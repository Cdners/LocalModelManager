from __future__ import annotations

import hashlib
import os
import re
import shutil
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import truststore

from .config import atomic_json, read_json
from .jobs import Control, Interrupted
from . import __version__


def client(network=None, **kwargs) -> httpx.Client:
    from .network import client_options
    return httpx.Client(**client_options(network),
                        timeout=httpx.Timeout(30, connect=10), follow_redirects=True,
                        headers={"User-Agent": f"LocalModelManager/{__version__}"}, **kwargs)


def request_json(url, control=None, method="GET", **kwargs):
    control = control or Control()
    for attempt in range(4):
        control.check()
        try:
            with client(network=control.network) as session:
                result = session.request(method, url, **kwargs)
                result.raise_for_status()
                return result.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"{urlsplit(url).netloc}: HTTP {exc.response.status_code}") from None
            if attempt == 3:
                raise RuntimeError(f"Network request failed: {urlsplit(url).netloc} ({type(exc).__name__})") from None
            control.wait(2**attempt)


def sha256(path: Path, control=None):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024**2):
            if control: control.check()
            digest.update(chunk)
    return digest.hexdigest()


class DownloadManager:
    """The application's resumable transfer path; only verified files are promoted."""
    def __init__(self, session_factory=None):
        self.session_factory = session_factory

    def download(self, url: str, target: Path, control: Control, progress=lambda _: None,
                 expected_size: int | None = None, expected_sha: str | None = None,
                 headers: dict | None = None, etag: str | None = None) -> dict:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        state_path = partial.with_name(partial.name + ".json")
        identity = hashlib.sha256(url.encode()).hexdigest()
        saved = read_json(state_path, {})
        if saved and (saved.get("identity") != identity or saved.get("sha256") != expected_sha):
            partial.unlink(missing_ok=True)
            saved = {}
        if target.exists():
            if (expected_size is None or target.stat().st_size == expected_size) and expected_sha and sha256(target, control) == expected_sha:
                return {"path": str(target), "size": target.stat().st_size, "sha256": expected_sha, "etag": etag}
            raise ValueError(f"Destination already exists and is not verified: {target.name}")
        for attempt in range(5):
            control.check()
            offset = partial.stat().st_size if partial.exists() else 0
            if expected_size is not None:
                if offset > expected_size:
                    partial.unlink(); offset = 0
                needed = max(0, expected_size - offset) + 64 * 1024**2
                if shutil.disk_usage(target.parent).free < needed:
                    raise ValueError("Not enough free disk space for this download.")
            request_headers = {'Accept-Encoding': 'identity'} | dict(headers or {})
            if offset:
                request_headers["Range"] = f"bytes={offset}-"
                if saved.get("etag"):
                    request_headers["If-Range"] = saved["etag"]
            try:
                if expected_size and offset == expected_size:
                    break
                factory = self.session_factory or (lambda: client(network=control.network))
                with factory() as session, session.stream("GET", url, headers=request_headers) as response:
                    if response.status_code == 416 and expected_size and offset == expected_size:
                        break
                    response.raise_for_status()
                    if response.status_code == 206:
                        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
                        if not match or int(match[1]) != offset:
                            raise ValueError("Invalid resume Content-Range; partial file was not appended.")
                        total = int(match[3])
                        if saved.get("etag") and response.headers.get("etag") and saved["etag"] != response.headers["etag"]:
                            raise ValueError("Remote ETag changed; partial download preserved. Resolve metadata again.")
                    else:
                        if offset:
                            raise ValueError("Server did not honor Range; partial download preserved instead of restarting.")
                        offset = 0
                        total = int(response.headers.get("content-length", 0)) or expected_size or 0
                    if expected_size is not None and total and total != expected_size:
                        raise ValueError("Remote file size differs from the pinned metadata.")
                    if not total:
                        raise ValueError("Remote file size is unavailable; refusing an unbounded download.")
                    if shutil.disk_usage(target.parent).free < total - offset + 64 * 1024**2:
                        raise ValueError("Not enough free disk space.")
                    saved = {"identity": identity, "etag": response.headers.get("etag", etag), "size": total, "sha256": expected_sha}
                    atomic_json(state_path, saved)
                    started = time.monotonic(); initial = offset; last_emit = 0.0
                    slow_since = None
                    with partial.open("ab" if offset else "wb") as handle:
                        for chunk in response.iter_bytes(64 * 1024):
                            control.check()
                            handle.write(chunk); offset += len(chunk)
                            if offset > total:
                                raise ValueError("Download exceeded the declared size.")
                            elapsed = max(0.001, time.monotonic() - started)
                            if elapsed - last_emit > 0.2 or offset == total:
                                speed = (offset - initial) / elapsed
                                slow_since = (slow_since or elapsed) if speed < 500 * 1024 else None
                                progress({"downloaded": offset, "total": total, "speed": speed,
                                          "eta": (total-offset)/speed if speed else None, "file": target.name,
                                          "detail": "Slow download: pause to change proxy or retry." if slow_since is not None and elapsed-slow_since >= 10 else ""})
                                last_emit = elapsed
                        handle.flush()
                        os.fsync(handle.fileno())
                    if offset != total:
                        raise httpx.ReadError("Incomplete response.")
                    expected_size = total
                break
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise RuntimeError(f"Download HTTP {exc.response.status_code}: {target.name}") from None
                if attempt == 4:
                    raise RuntimeError(f"Download interrupted after retries. Resume is available: {target.name}") from None
                progress({"detail": f"Network retry {attempt+1}/4"})
                control.wait(2**attempt)
        control.check()
        if not partial.exists() or partial.stat().st_size != expected_size:
            raise ValueError("Downloaded file size verification failed.")
        progress({"detail": "Verifying SHA-256"})
        digest = sha256(partial, control)
        if expected_sha and digest.lower() != expected_sha.lower():
            partial.unlink(missing_ok=True)
            state_path.unlink(missing_ok=True)
            raise ValueError("SHA-256 mismatch; invalid data removed, installed files preserved.")
        partial.replace(target)
        state_path.unlink(missing_ok=True)
        return {"path": str(target), "size": target.stat().st_size, "sha256": digest, "etag": saved.get("etag", etag)}

# Backwards-compatible import for existing integrations.
Downloader = DownloadManager


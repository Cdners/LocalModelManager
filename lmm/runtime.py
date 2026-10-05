from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .config import Store, atomic_json, read_json
from .jobs import Control
from .net import Downloader, request_json

RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_binary(executable: Path, *args, timeout=30):
    result = subprocess.run([str(executable), *args], cwd=executable.parent,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=NO_WINDOW)
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode:
        raise RuntimeError(f"{executable.name} failed ({result.returncode}): {output[-1500:]}")
    return output


def hardware():
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("This runtime installer requires Windows x64.")
    if os.name != "nt":
        raise ValueError("Windows runtime installation is only available on Windows.")
    result = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
    if result.returncode or not result.stdout.strip():
        raise ValueError("NVIDIA GPU/driver not detected. CPU-only runtime will not be installed.")
    cuda = ctypes.WinDLL("nvcuda.dll")
    version = ctypes.c_int()
    if cuda.cuInit(0) != 0 or cuda.cuDriverGetVersion(ctypes.byref(version)) != 0:
        raise ValueError("NVIDIA CUDA driver could not initialize.")
    return {"gpu": result.stdout.strip(), "cuda_driver": version.value,
            "cuda_major": version.value // 1000, "cuda_minor": version.value % 1000 // 10, "arch": "x64"}


def select_assets(assets: list[dict], cuda_major: int) -> list[dict]:
    candidates = []
    for asset in assets:
        name = asset["name"].lower()
        match = re.search(r"cuda[-_](\d+)(?:\.(\d+))?", name)
        if not (match and "win" in name and re.search(r"x64|amd64|x86_64", name) and name.endswith(".zip")):
            continue
        if any(x in name for x in ("cudart", "arm64", "debug")):
            continue
        version = (int(match[1]), int(match[2] or 0))
        if version[0] <= cuda_major:
            candidates.append((version, asset))
    if not candidates:
        raise ValueError("Release has no compatible Windows x64 CUDA package. CPU fallback is disabled.")
    version, main = max(candidates, key=lambda item: item[0])
    marker = f"cuda-{version[0]}.{version[1]}"
    companions = [a for a in assets if "cudart" in a["name"].lower() and "win" in a["name"].lower()
                  and marker in a["name"].lower() and "x64" in a["name"].lower() and a["name"].endswith(".zip")]
    return [main] + companions


def latest_release(control: Control, cuda_major: int):
    release = request_json(RELEASE_API + "/latest", control)
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Expected the latest stable llama.cpp release.")
    stable_tag = release["tag_name"]
    try:
        assets = select_assets(release["assets"], cuda_major)
    except ValueError:
        # New ggml stable releases point to the matching binary/nightly build.
        match = re.search(r"https://github\.com/ggml-org/llama\.cpp/releases/tag/([\w.-]+)", release.get("body", ""))
        if not match or not any(a["name"] == "nightly-tag.txt" for a in release["assets"]):
            raise
        release = request_json(RELEASE_API + "/tags/" + match[1], control)
        assets = select_assets(release["assets"], cuda_major)
    return {"stable_tag": stable_tag, "binary_tag": release["tag_name"], "assets": assets,
            "source_url": release["html_url"], "published_at": release.get("published_at")}


def safe_extract(archive: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        if sum(i.file_size for i in bundle.infolist()) > shutil.disk_usage(root).free - 64 * 1024**2:
            raise ValueError("Insufficient disk space to extract archive.")
        for item in bundle.infolist():
            destination = (root / item.filename).resolve()
            if not destination.is_relative_to(root) or item.filename.startswith(("/", "\\")) or ":" in item.filename:
                raise ValueError("Unsafe archive path.")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive links are not allowed.")
        bundle.extractall(root)


class Runtime:
    def __init__(self, store: Store):
        self.store = store

    @property
    def executable(self):
        return self.store.runtime / "llama-server.exe"

    def installed(self):
        return read_json(self.store.runtime / "runtime_info.json", {})

    def check(self, control, progress=lambda _: None):
        info = hardware()
        release = latest_release(control, info["cuda_major"])
        release["hardware"] = info
        atomic_json(self.store.config / "runtime_latest.json", release)
        return release

    def stage(self, release, control, progress=lambda _: None):
        cache = self.store.root / "downloads" / "runtime" / release["binary_tag"]
        cache.mkdir(parents=True, exist_ok=True)
        parent = self.store.runtime.parent; parent.mkdir(parents=True, exist_ok=True)
        stage = parent / (".llama-stage-" + uuid.uuid4().hex)
        stage.mkdir()
        try:
            receipts = []
            for asset in release["assets"]:
                control.check()
                digest = asset.get("digest", "") or ""
                expected = digest.removeprefix("sha256:") if digest.startswith("sha256:") else None
                receipt = Downloader().download(asset["browser_download_url"], cache / asset["name"], control,
                    progress, asset["size"], expected)
                receipts.append(receipt)
                safe_extract(Path(receipt["path"]), stage)
            servers = list(stage.rglob("llama-server.exe"))
            if len(servers) != 1:
                raise ValueError("Runtime package must contain one llama-server.exe.")
            binary_dir = servers[0].parent
            if binary_dir != stage:
                for file in binary_dir.iterdir():
                    if file.is_file(): shutil.copy2(file, stage / file.name)
            # Companion archives may use their own subdirectory.
            for dll in list(stage.rglob("*.dll")):
                if dll.parent != stage and not (stage / dll.name).exists(): shutil.copy2(dll, stage / dll.name)
            if not list(stage.glob("*cuda*.dll")):
                raise ValueError("CUDA backend DLL is missing.")
            progress({"detail": "Checking runtime version and CUDA device"})
            version = run_binary(stage / "llama-server.exe", "--version")
            devices = run_binary(stage / "llama-server.exe", "--list-devices", timeout=45)
            if not re.search(r"CUDA\d|NVIDIA", devices, re.I):
                raise ValueError("Runtime cannot see a CUDA GPU. Existing runtime preserved. " + devices[-600:])
            info = {"version": version, "release_tag": release["stable_tag"], "binary_tag": release["binary_tag"],
                    "installed_at": datetime.now(timezone.utc).isoformat(), "source_url": release["source_url"],
                    "backend": "CUDA", "devices": devices, "assets": receipts}
            atomic_json(stage / "runtime_info.json", info)
            atomic_json(self.store.config / "runtime_staged.json", {"path": str(stage), "info": info})
            return stage
        except BaseException:
            if stage.exists() and stage.resolve().parent == parent.resolve() and stage.name.startswith(".llama-stage-"):
                shutil.rmtree(stage)
            raise

    def install(self, stage: Path, control, stop=lambda: [], start=lambda ids: None, health=lambda ids: None):
        target = self.store.runtime
        stage = Path(stage).resolve()
        if stage.parent != target.parent.resolve() or not stage.name.startswith(".llama-stage-"):
            raise ValueError("Runtime staging directory is outside the managed parent.")
        if not (stage / "runtime_info.json").exists() or not (stage / "llama-server.exe").exists():
            raise ValueError("Runtime stage has not been verified.")
        if target.exists() and any(target.iterdir()) and not (target / "runtime_info.json").exists():
            raise ValueError("Runtime directory contains unmanaged files; choose an empty directory.")
        control.check()
        running = stop()
        backup = target.with_name(".llama-backup-" + uuid.uuid4().hex)
        old_exists = target.exists()
        swapped = False
        journal = self.store.config / "runtime_transaction.json"
        atomic_json(journal, {"target": str(target), "stage": str(stage), "backup": str(backup), "profiles": running, "old_exists": old_exists, "state": "prepared"})
        try:
            if old_exists: target.rename(backup)
            stage.rename(target); swapped = True
            start(running); health(running)
            atomic_json(journal, {"state": "complete", "backup": str(backup), "target": str(target)})
            (self.store.config / "runtime_staged.json").unlink(missing_ok=True)
            return self.installed()
        except Exception as exc:
            try:
                stop()
                if swapped and target.exists(): target.rename(stage)
                if old_exists and backup.exists(): backup.rename(target)
                start(running); health(running)
                atomic_json(journal, {"state": "rolled_back", "reason": str(exc), "target": str(target)})
            except Exception as rollback:
                raise RuntimeError(f"Runtime update failed; recovery needed. Backup: {backup}. {rollback}") from exc
            raise RuntimeError(f"Runtime update failed; previous runtime restored: {exc}") from exc

    def recover(self, manager):
        journal=self.store.config/"runtime_transaction.json"
        data=read_json(journal,{})
        if data.get("state")!="prepared":return None
        target=Path(data["target"]).resolve(); backup=Path(data["backup"]).resolve()
        stage=Path(data["stage"]).resolve()
        if target!=self.store.runtime or backup.parent!=target.parent or not backup.name.startswith(".llama-backup-") or stage.parent!=target.parent or not stage.name.startswith(".llama-stage-"):
            raise ValueError("Runtime recovery paths do not match this installation.")
        ids=data.get("profiles",[])
        with manager.lock:
            for identity in ids:manager.stop(identity)
            if backup.exists():
                if target.exists():target.rename(target.with_name(".llama-stage-recovered-"+uuid.uuid4().hex))
                backup.rename(target)
            manager.start_many(ids); manager.wait_ready_many(ids)
        atomic_json(journal,data|{"state":"recovered"})
        return "Recovered an interrupted runtime update."


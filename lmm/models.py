from __future__ import annotations

import re
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from huggingface_hub import hf_hub_url
from huggingface_hub.utils import validate_repo_id

from .config import Store, atomic_json, read_json
from .jobs import Control
from .net import Downloader, request_json

RECOMMENDED_REPO = "ggml-org/Qwen3-ASR-1.7B-GGUF"


def match_mmproj(filename: str, files: list[str]) -> str | None:
    main = PurePosixPath(filename)
    direct = main.with_name("mmproj-" + main.name).as_posix()
    lower = {name.lower(): name for name in files}
    if direct.lower() in lower:
        return lower[direct.lower()]
    quant = re.search(r"(?:^|[-_.])(Q\d(?:_[A-Z0-9]+)*|BF16|F16|F32)(?=\.|-|$)", main.name, re.I)
    candidates = [f for f in files if PurePosixPath(f).name.lower().startswith("mmproj") and f.lower().endswith(".gguf")]
    if quant:
        matching = [f for f in candidates if re.search(r"(?:^|[-_.])" + re.escape(quant[1]) + r"(?=\.|-|$)", PurePosixPath(f).name, re.I)]
        if len(matching) == 1: return matching[0]
    # A single generic projection file is unambiguous within the selected repo.
    if len(candidates) == 1 and re.fullmatch(r"mmproj(?:[-_.](?:f16|bf16|f32))?\.gguf", PurePosixPath(candidates[0]).name, re.I):
        return candidates[0]
    return None


def model_metadata(data: dict) -> dict:
    revision = data.get("sha", "")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
        raise ValueError("Hugging Face did not return an immutable commit revision.")
    files = []
    for item in data.get("siblings", []):
        name = item["rfilename"]
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe repository filename.")
        if not name.lower().endswith(".gguf"): continue
        lfs = item.get("lfs") or {}
        files.append({"filename": name, "size": lfs.get("size", item.get("size")),
                      "sha256": lfs.get("sha256") or lfs.get("oid"), "etag": lfs.get("sha256") or item.get("blobId"),
                      "is_mmproj": path.name.lower().startswith("mmproj")})
    return {"repo_id": data.get("id", data.get("modelId")), "revision": revision, "files": files}


class Models:
    def __init__(self, store: Store, token=lambda: ""):
        self.store = store
        self.token = token
        self.lock = threading.RLock()
        self.index_path = store.config / "models.json"

    def headers(self):
        value = self.token()
        return {"Authorization": f"Bearer {value}"} if value else {}

    def search(self, query, control):
        return request_json("https://huggingface.co/api/models", control, params={"search": query, "filter": "gguf", "limit": 30}, headers=self.headers())

    def repository(self, repo_id, control, revision="main"):
        validate_repo_id(repo_id)
        data = request_json(f"https://huggingface.co/api/models/{repo_id}/revision/{quote(revision, safe='')}?blobs=true", control, headers=self.headers())
        return model_metadata(data)

    def installed(self):
        records = read_json(self.index_path, [])
        for record in records:
            path = self.store.path(record["path"])
            record["valid"] = path.is_file() and path.stat().st_size == record["size"]
        return records

    def download(self, metadata, filenames, control, progress=lambda _: None):
        repo = metadata["repo_id"]
        validate_repo_id(repo)
        by_name = {f["filename"]: f for f in metadata["files"]}
        revision = metadata["revision"]
        root = self.store.models / repo.replace("/", "__") / revision[:12]
        receipts = []
        for filename in filenames:
            if filename not in by_name: raise ValueError("Selected file is not in the pinned repository listing.")
            info = by_name[filename]
            target = (root / filename).resolve()
            if not target.is_relative_to(root.resolve()): raise ValueError("Unsafe model path.")
            if not info["size"]: raise ValueError("Remote model size is missing.")
            url = hf_hub_url(repo, filename, revision=revision)
            if target.exists() and not info.get("sha256"):
                records = self.installed()
                existing = next((r for r in records if r["path"] == self.store.relative(target) and r.get("valid")), None)
                if not existing: raise ValueError("Unverified file already exists; choose another model directory.")
                result = {"sha256": existing["sha256"], "size": existing["size"], "etag": existing.get("etag")}
            else:
                result = Downloader().download(url, target, control, progress, info["size"], info.get("sha256"), self.headers(), info.get("etag"))
            record = {"repo_id": repo, "filename": filename, "revision": revision,
                      "etag": info.get("etag") or result.get("etag"), "size": result["size"],
                      "sha256": result["sha256"], "downloaded_at": datetime.now(timezone.utc).isoformat(),
                      "path": self.store.relative(target), "is_mmproj": info["is_mmproj"], "status": "complete"}
            atomic_json(target.with_name(target.name+".metadata.json"), record)
            with self.lock:
                records = read_json(self.index_path, [])
                records = [r for r in records if r["path"] != record["path"]] + [record]
                atomic_json(self.index_path, records)
            receipts.append(record)
        return receipts

    def check_updates(self, control, progress=lambda _: None):
        records = [r for r in self.installed() if r["valid"]]
        results = []
        for repo in sorted({r["repo_id"] for r in records}):
            control.check()
            metadata = self.repository(repo, control)
            files = {f["filename"]: f for f in metadata["files"]}
            for record in [r for r in records if r["repo_id"] == repo]:
                remote = files.get(record["filename"])
                if not remote:
                    results.append({"record": record, "status": "Remote file removed", "metadata": metadata})
                else:
                    changed = bool(remote.get("sha256") and remote["sha256"] != record.get("sha256")) or remote["size"] != record["size"]
                    if not remote.get("sha256"):
                        changed |= remote.get("etag") != record.get("etag")
                    results.append({"record": record, "status": "Update available" if changed else "Up to date", "metadata": metadata})
        atomic_json(self.store.config / "model_updates.json", results)
        return results

    def apply_profile_paths(self, old_records, new_records, manager):
        replacement = {(r["repo_id"], r["filename"]): r["path"] for r in new_records}
        paths = {self.store.path(r["path"]): replacement[(r["repo_id"], r["filename"])]
                 for r in old_records if (r["repo_id"], r["filename"]) in replacement}
        originals = [asdict(p) for p in self.store.profiles]
        affected = [p.id for p in self.store.profiles if self.store.path(p.model_path) in paths or (p.mmproj_path and self.store.path(p.mmproj_path) in paths)]
        running = [pid for pid in affected if manager.is_running(pid)]
        journal=self.store.config/"model_transaction.json"
        atomic_json(journal,{"state":"prepared","profiles":originals,"running":running})
        for pid in running: manager.stop(pid)
        try:
            for profile in self.store.profiles:
                if self.store.path(profile.model_path) in paths: profile.model_path = paths[self.store.path(profile.model_path)]
                if profile.mmproj_path and self.store.path(profile.mmproj_path) in paths: profile.mmproj_path = paths[self.store.path(profile.mmproj_path)]
            self.store.save()
            manager.start_many(running); manager.wait_ready_many(running)
            atomic_json(journal,{"state":"complete"})
        except Exception:
            for pid in running: manager.stop(pid)
            from .config import Profile
            self.store.profiles = [Profile.from_dict(p) for p in originals]; self.store.save()
            manager.start_many(running); manager.wait_ready_many(running)
            atomic_json(journal,{"state":"rolled_back"})
            raise
        return affected

    def recover(self, manager):
        data=read_json(self.store.config/"model_transaction.json",{})
        if data.get("state")!="prepared":return
        from .config import Profile
        with manager.lock:
            for identity in data["running"]:manager.stop(identity)
            self.store.profiles=[Profile.from_dict(p) for p in data["profiles"]]; self.store.save()
            manager.start_many(data["running"]); manager.wait_ready_many(data["running"])
        atomic_json(self.store.config/"model_transaction.json",{"state":"recovered"})


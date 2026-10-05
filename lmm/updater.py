from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid

from packaging.version import Version, InvalidVersion
import psutil

from . import __version__
from .config import atomic_json, read_json
from .jobs import Control
from .net import Downloader, request_json
from .processes import launch_application, launch_hidden, process_identity, verify_identity
from .runtime import safe_extract

APP_FILES=("LocalModelManager.exe","app","app_manifest.json")


def newer(version, current=__version__):
    return Version(version.lstrip("v")) > Version(current.lstrip("v"))


def parse_manifest(data):
    if not isinstance(data,dict):raise ValueError("Update manifest must be a JSON object.")
    for key in ("version","url","sha256"):
        if not isinstance(data.get(key),str) or not data[key]:raise ValueError(f"Update manifest needs {key}.")
    try:Version(data["version"].lstrip("v"))
    except InvalidVersion as exc:raise ValueError("Invalid update version.") from exc
    url=urlsplit(data["url"])
    if url.scheme!="https" and not (url.scheme=="http" and url.hostname in {"localhost","127.0.0.1","::1"}):
        raise ValueError("Update packages must use HTTPS (HTTP allowed only on loopback for testing).")
    if url.username or url.password:raise ValueError("Do not embed credentials in update URLs.")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",data["sha256"]):raise ValueError("Update SHA-256 must contain 64 hex characters.")
    return {"version":data["version"],"url":data["url"],"sha256":data["sha256"].lower(),"notes":str(data.get("notes","")),"size":data.get("size")}


def check(provider, source, control):
    if not source.strip():return {"configured":False,"status":"App update source not configured"}
    if provider=="manifest":data=request_json(source,control)
    elif provider=="github":
        repo=source.strip().removeprefix("https://github.com/").removesuffix("/")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+",repo):raise ValueError("Use GitHub owner/repo.")
        release=request_json(f"https://api.github.com/repos/{repo}/releases/latest",control)
        candidates=[a for a in release.get("assets",[]) if a["name"].lower().endswith(".zip") and "localmodelmanager" in a["name"].lower().replace("-","") and "arm" not in a["name"].lower()]
        if len(candidates)!=1:raise ValueError("The GitHub release must have exactly one LocalModelManager Windows x64 ZIP asset.")
        asset=candidates[0]; digest=asset.get("digest") or ""
        data={"version":release["tag_name"],"url":asset["browser_download_url"],"sha256":digest.removeprefix("sha256:"),"size":asset["size"],"notes":release.get("body","")}
    else:raise ValueError("Unknown app update provider.")
    manifest=parse_manifest(data)
    return manifest | {"configured":True,"available":newer(manifest["version"]),"status":"Update available" if newer(manifest["version"]) else "Up to date"}


def stage(store, manifest, control, progress=lambda _:None):
    manifest=parse_manifest(manifest)
    cache=store.root/"downloads"/"app"/(manifest["sha256"]+".zip")
    Downloader().download(manifest["url"],cache,control,progress,manifest.get("size"),manifest["sha256"])
    staging=store.root/"updates"/("app-stage-"+uuid.uuid4().hex)
    safe_extract(cache,staging)
    executables=list(staging.rglob("LocalModelManager.exe"))
    if len(executables)!=1:raise ValueError("Update archive must contain one LocalModelManager.exe.")
    source=executables[0].parent
    info=read_json(source/"app_manifest.json",{})
    if not (source/"app").is_dir() or info.get("product")!="LocalModelManager" or Version(info.get("version","0"))!=Version(manifest["version"].lstrip("v")):
        raise ValueError("Package identity/version does not match its update manifest.")
    if source!=staging:
        for name in APP_FILES:shutil.move(str(source/name),str(staging/name))
    atomic_json(staging/"verified.json",manifest)
    atomic_json(store.config/"app_staged.json",{"path":str(staging),"manifest":manifest})
    return str(staging)


def swap_application(root: Path, staging: Path, backup: Path, start_and_verify, stop_new=lambda:None):
    """Only the three application payload paths are moved. Persistent data never enters the swap."""
    root=root.resolve(); staging=staging.resolve(); backup=backup.resolve()
    for path,prefix in ((staging,"app-stage-"),(backup,"app-backup-")):
        if path.parent!=root/"updates" or not path.name.startswith(prefix):raise ValueError("App update paths are outside the managed updates directory.")
    if any(not (staging/n).exists() for n in APP_FILES):raise ValueError("App package is incomplete.")
    backup.mkdir(exist_ok=False)
    journal=root/"updates"/"transaction.json"
    transaction={"root":str(root),"stage":str(staging),"backup":str(backup),"state":"prepared","old":[],"new":[]}
    atomic_json(journal,transaction)
    try:
        for name in APP_FILES:
            if (root/name).exists():
                (root/name).rename(backup/name); transaction["old"].append(name); atomic_json(journal,transaction)
            (staging/name).rename(root/name); transaction["new"].append(name); atomic_json(journal,transaction)
        transaction["state"]="verifying"; atomic_json(journal,transaction)
        if not start_and_verify():raise RuntimeError("The updated application did not acknowledge a healthy startup.")
        transaction["state"]="complete"; atomic_json(journal,transaction)
    except Exception as exc:
        stop_new()
        for name in reversed(transaction["new"]):
            if (root/name).exists():(root/name).rename(staging/name)
        for name in reversed(transaction["old"]):
            if (backup/name).exists():(backup/name).rename(root/name)
        transaction.update(state="rolled_back",reason=str(exc)); atomic_json(journal,transaction)
        raise


def prepare_helper(store, staging, running_profiles):
    if not getattr(sys,"frozen",False):raise ValueError("请在打包后的 EXE 中安装软件更新；源码运行支持检查与下载。")
    staging=Path(staging).resolve()
    if staging.parent!=store.root/"updates" or not staging.name.startswith("app-stage-") or not (staging/"verified.json").is_file():
        raise ValueError("App update stage was not verified.")
    for identity in running_profiles:
        record=read_json(store.config/"processes"/(identity+".json"),{})
        supervisor=record.get("supervisor",{}); deadline=time.monotonic()+8
        while verify_identity(supervisor) and time.monotonic()<deadline:time.sleep(.1)
        if verify_identity(supervisor):raise RuntimeError("A model supervisor is still exiting. Retry the app update shortly.")
    helper=store.root/"updates"/("app-helper-"+uuid.uuid4().hex); helper.mkdir()
    # A private helper copy keeps loaded EXE/DLL files outside both the old and new payload.
    for name in APP_FILES:
        source=store.root/name
        if source.is_dir():shutil.copytree(source,helper/name)
        else:shutil.copy2(source,helper/name)
    key=uuid.uuid4().hex
    job=store.root/"updates"/(key+".job.json")
    atomic_json(job,{"root":str(store.root),"stage":str(staging),"parent":process_identity(os.getpid()),
        "ack":str(store.root/"updates"/(key+".ack.json")),"key":key,"profiles":running_profiles})
    process=launch_hidden([str(helper/"LocalModelManager.exe"),"--apply-update",str(job)],store.root)
    return process.pid


def apply_job(job_path: Path):
    job_path=job_path.resolve(); job=read_json(job_path,{})
    root=Path(job["root"]).resolve()
    if job_path.parent!=root/"updates":raise ValueError("Update job location is invalid.")
    ack=Path(job["ack"]).resolve()
    if ack.parent!=root/"updates" or ack.name!=job["key"]+".ack.json":raise ValueError("Update acknowledgement path is invalid.")
    if Path(job["parent"]["executable"]).resolve()!=root/"LocalModelManager.exe":raise ValueError("Updater may only replace its parent application.")
    deadline=time.monotonic()+90
    while verify_identity(job["parent"]) and time.monotonic()<deadline:time.sleep(.2)
    if verify_identity(job["parent"]):raise TimeoutError("Manager did not exit. No application files were changed.")
    child={}
    def start():
        process=launch_application([str(root/"LocalModelManager.exe"),"--root",str(root),"--update-ack",str(job_path)],root)
        child.update(process_identity(process.pid))
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if ack.exists() and read_json(ack,{}).get("key")==job["key"]:return True
            if process.poll() is not None:return False
            time.sleep(.2)
        return False
    def stop_new():
        if verify_identity(child):
            process=psutil.Process(child["pid"]); process.terminate()
            try:process.wait(8)
            except psutil.TimeoutExpired:
                if verify_identity(child):process.kill(); process.wait(5)
    try:
        swap_application(root,Path(job["stage"]),root/"updates"/("app-backup-"+job["key"]),start,stop_new)
        (root/"config"/"app_staged.json").unlink(missing_ok=True)
        return 0
    except Exception:
        atomic_json(root/"config"/"resume_profiles.json",job.get("profiles",[]))
        launch_application([str(root/"LocalModelManager.exe"),"--root",str(root)],root)
        raise


def acknowledge(job_path: Path, store):
    job=read_json(job_path,{})
    if job_path.resolve().parent!=store.root/"updates" or Path(job["root"]).resolve()!=store.root:raise ValueError("Invalid app update acknowledgement.")
    ack=Path(job["ack"]).resolve()
    if ack.parent!=store.root/"updates" or ack.name!=job["key"]+".ack.json":raise ValueError("Invalid update acknowledgement path.")
    atomic_json(ack,{"key":job["key"],"version":__version__,"pid":os.getpid()})
    return job.get("profiles",[])

from __future__ import annotations

import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid

import psutil

from .config import Profile, Store, atomic_json, read_json
from .runtime import run_binary


def process_identity(pid: int) -> dict:
    process = psutil.Process(pid)
    return {"pid": pid, "create_time": process.create_time(), "executable": str(Path(process.exe()).resolve()), "command_line": process.cmdline()}


def verify_identity(record: dict, process_factory=psutil.Process) -> bool:
    try:
        process = process_factory(int(record["pid"]))
        return (process.is_running() and abs(process.create_time() - record["create_time"]) < 0.01
                and os.path.normcase(os.path.realpath(process.exe())) == os.path.normcase(os.path.realpath(record["executable"]))
                and process.cmdline() == record["command_line"])
    except (psutil.Error, KeyError, TypeError, ValueError, OSError):
        return False


def port_available(host: str, port: int) -> bool:
    host = "127.0.0.1" if host == "localhost" else host
    try:
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as sock:
            if os.name == "nt": sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def build_command(profile: Profile, store: Store, help_text: str) -> list[str]:
    from .adapters import get_adapter
    adapter = get_adapter(profile.runtime_id)
    adapter.require_implemented()
    if profile.type not in adapter.supported_tasks: raise ValueError('This runtime does not support the selected task.')
    return adapter.build_launch_command(profile, store, help_text)


def build_llama_command(profile: Profile, store: Store, help_text: str) -> list[str]:
    profile.validate()
    executable = store.runtime / "llama-server.exe"
    model = store.path(profile.model_path)
    if not model.is_file() or model.suffix.lower() != ".gguf":
        raise ValueError("A complete main GGUF file is required.")
    if profile.requires_mmproj and not profile.mmproj_path:
        # Imported local pairs get the same conservative matching behavior.
        from .models import match_mmproj
        matched = match_mmproj(model.name, [f.name for f in model.parent.glob("*.gguf")])
        if matched: profile.mmproj_path = store.relative(model.parent / matched); store.save()
        else: raise ValueError("该模型需要 MMProj，但未找到兼容文件。")
    command = [str(executable)]
    def flag(names, value):
        selected = next((name for name in names if re.search(r"(?<![\w-])"+re.escape(name)+r"(?=[ ,=\t\n]|$)", help_text)), None)
        if not selected: raise ValueError("Runtime does not support " + "/".join(names))
        command.extend([selected, str(value)])
    flag(["--model", "-m"], model)
    if profile.mmproj_path:
        mmproj = store.path(profile.mmproj_path)
        if not mmproj.is_file() or mmproj.suffix.lower() != ".gguf": raise ValueError("MMProj file is missing or incomplete.")
        flag(["--mmproj", "-mm"], mmproj)
    flag(["--host"], profile.host); flag(["--port"], profile.port)
    if profile.backend == 'vulkan': raise ValueError('This llama.cpp installation uses CUDA; select CUDA or CPU.')
    flag(["--n-gpu-layers", "--gpu-layers", "-ngl"], 0 if profile.backend == 'cpu' else profile.gpu_layers)
    flag(["--parallel", "-np"], profile.parallel)
    if "--alias" in help_text: flag(["--alias", "-a"], profile.id)
    if profile.type in {'embedding', 'reranker'}:
        if '--embedding' not in help_text: raise ValueError('Runtime does not advertise embedding support.')
        command.append('--embedding')
    if profile.type == 'reranker':
        if '--reranking' not in help_text: raise ValueError('Runtime does not advertise reranking support.')
        command.append('--reranking')
    # Keep the initial GPU footprint bounded; the profile can explicitly override it.
    if "--ctx-size" in help_text and not any(a.split("=")[0] in {"--ctx-size", "-c"} for a in profile.extra_args):
        flag(["--ctx-size", "-c"], 4096)
    for argument in profile.extra_args:
        if argument.startswith("--") and argument.split("=", 1)[0] not in help_text:
            raise ValueError(f"This runtime does not advertise {argument}.")
    command.extend(profile.extra_args)
    return command


def helper_command(*args):
    if getattr(sys, "frozen", False): return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve().parents[1]/"main.py"), *args]


def launch_hidden(command, cwd):
    options = {"cwd": str(cwd), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        info = subprocess.STARTUPINFO(); info.dwFlags |= subprocess.STARTF_USESHOWWINDOW; info.wShowWindow = 0
        options.update(creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=info)
    else: options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def launch_application(command, cwd):
    options = {"cwd": str(cwd), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        info = subprocess.STARTUPINFO(); info.dwFlags |= subprocess.STARTF_USESHOWWINDOW; info.wShowWindow = 1
        options["startupinfo"] = info
    return subprocess.Popen(command, **options)


class Manager:
    def __init__(self, store: Store):
        self.store = store
        self.lock = threading.RLock()
        self.records = store.config/"processes"; self.records.mkdir(exist_ok=True)

    def record(self, profile_id):
        return read_json(self.records/(profile_id+".json"), {})

    def is_running(self, profile_id):
        return verify_identity(self.record(profile_id))

    def state(self, profile_id):
        record = self.record(profile_id)
        if verify_identity(record): return record | {"state": "RUNNING"}
        if record.get("pid") and psutil.pid_exists(record["pid"]): return record | {"state": "IDENTITY MISMATCH"}
        return record | {"state": "STOPPED"}

    def start(self, profile_id):
        with self.lock:
            profile = self.store.get_profile(profile_id)
            if self.is_running(profile_id): return self.record(profile_id)
            ports = {profile.port} | ({profile.proxy_port} if profile.compatibility_proxy else set())
            for other in self.store.profiles:
                if other.id != profile_id and self.is_running(other.id):
                    other_ports = {other.port} | ({other.proxy_port} if other.compatibility_proxy else set())
                    if ports & other_ports: raise ValueError(f"Port conflict with managed profile {other.name}.")
            for port in ports:
                if not port_available(profile.host if port == profile.port else "127.0.0.1", port):
                    raise ValueError(f"Port {port} is already in use. Existing services were not modified.")
            from .adapters import get_adapter
            adapter = get_adapter(profile.runtime_id); adapter.require_implemented()
            executable = adapter.executable(self.store)
            if not executable.exists(): raise ValueError(adapter.name + ': runtime is not installed.')
            help_text = run_binary(executable, "--help", timeout=30) if executable.suffix == '.exe' else ''
            command = build_command(profile, self.store, help_text)
            session = uuid.uuid4().hex
            spec = {"session": session, "profile_id": profile.id, "command": command,
                    "cwd": str(adapter.runtime_dir(self.store)), "record": str(self.records/(profile.id+".json")),
                    "log": str(self.store.logs/(profile.id+".log")),
                    "stop_file": str(self.records/(session+".stop")),
                    "proxy": profile.compatibility_proxy, "proxy_port": profile.proxy_port, "port": profile.port,
                    "host": profile.host}
            job = self.records/(session+".job.json"); atomic_json(job, spec)
            supervisor = launch_hidden(helper_command("--supervise", str(job)), self.store.root)
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                record = self.record(profile_id)
                if record.get("session") == session:
                    if record.get("error"): raise RuntimeError(record["error"])
                    if verify_identity(record): return record
                if supervisor.poll() is not None: raise RuntimeError("Model supervisor exited; check the profile log.")
                time.sleep(0.1)
            raise RuntimeError("Server startup identity was not confirmed. Inspect process recovery before retrying.")

    def stop(self, profile_id):
        with self.lock:
            record = self.record(profile_id)
            if not verify_identity(record):
                if record.get("pid") and psutil.pid_exists(record["pid"]):
                    raise ValueError("PID identity has changed; refusing to signal this process.")
                self.wait_supervisor(record)
                return
            stop_path = Path(record["stop_file"])
            if stop_path.resolve().parent != self.records.resolve() or stop_path.name != record["session"]+".stop":
                raise ValueError("Untrusted process stop receipt.")
            stop_path.write_text(record["session"], encoding="utf-8")
            deadline=time.monotonic()+18
            while verify_identity(record) and time.monotonic() < deadline: time.sleep(0.15)
            if verify_identity(record):
                # Orphan supervisor: target one independently verified process only.
                graceful_break(record)
                deadline=time.monotonic()+5
                while verify_identity(record) and time.monotonic() < deadline: time.sleep(0.1)
                if verify_identity(record):
                    process=psutil.Process(record["pid"]); process.kill(); process.wait(timeout=5)
            if verify_identity(record): raise RuntimeError("Could not stop the managed process.")
            # The HTTP proxy lives in the supervisor. Releasing the llama PID alone
            # does not mean the profile's proxy port has been released yet.
            self.wait_supervisor(record)

    def wait_supervisor(self, record):
        supervisor=record.get("supervisor",{})
        deadline=time.monotonic()+10
        while verify_identity(supervisor) and time.monotonic()<deadline:time.sleep(.1)
        if verify_identity(supervisor):
            if verify_identity(record):raise RuntimeError("Model supervisor is still stopping the server.")
            # Server is gone; this verified manager helper can only hold its proxy/log.
            process=psutil.Process(supervisor["pid"]); process.terminate(); process.wait(timeout=5)

    def restart(self, profile_id):
        self.stop(profile_id)
        return self.start(profile_id)

    def switch(self, profile_id, control=None, progress=lambda _:None):
        """Replace only managed services sharing the target ports; restore on failure."""
        from .api import wait_ready
        from .jobs import Control
        control = control or Control()
        with self.lock:
            profile = self.store.get_profile(profile_id)
            if self.is_running(profile_id):
                return self.record(profile_id) | wait_ready(profile,lambda:self.is_running(profile_id),control=control)
            from .adapters import get_adapter
            adapter = get_adapter(profile.runtime_id)
            if not adapter.executable(self.store).exists(): raise ValueError('Install the selected runtime first.')
            if not self.store.path(profile.model_path).exists(): raise ValueError('Model file or directory is missing.')
            ports = {profile.port} | ({profile.proxy_port} if profile.compatibility_proxy else set())
            previous = [p.id for p in self.store.profiles if p.id != profile_id and self.is_running(p.id)
                        and ports & ({p.port} | ({p.proxy_port} if p.compatibility_proxy else set()))]
            stopped = []
            control.check()
            try:
                for identity in previous:
                    self.stop(identity); stopped.append(identity)
                control.check()
                record = self.start(profile_id)
                return record | wait_ready(profile,lambda:self.is_running(profile_id),control=control,progress=progress)
            except Exception:
                self.stop(profile_id)
                self.start_many(stopped); self.wait_ready_many(stopped)
                raise

    def stop_all(self):
        running = [p.id for p in self.store.profiles if self.is_running(p.id)]
        for pid in running: self.stop(pid)
        return running

    def stop_runtime(self, runtime_id):
        running = [p.id for p in self.store.profiles if p.runtime_id == runtime_id and self.is_running(p.id)]
        for identity in running: self.stop(identity)
        return running

    def start_many(self, ids):
        for pid in ids: self.start(pid)

    def wait_ready_many(self, ids):
        from .api import wait_ready
        for pid in ids: wait_ready(self.store.get_profile(pid), lambda: self.is_running(pid))


def graceful_break(record):
    if not verify_identity(record): return
    if os.name != "nt":
        os.kill(record["pid"], signal.SIGTERM); return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    # This path only runs in background workers/helpers; never targets a process by name.
    attached = kernel.AttachConsole(record["pid"])
    try:
        kernel.GenerateConsoleCtrlEvent(1, record["pid"])
    finally:
        if attached: kernel.FreeConsole()


def supervise(job_path: Path):
    job = read_json(job_path, None)
    record_path=Path(job["record"])
    logger=logging.getLogger("supervisor")
    Path(job["log"]).parent.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(job["log"], maxBytes=20*1024**2, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s")); logger.addHandler(handler); logger.setLevel(logging.INFO)
    proxy = None
    try:
        if os.name == "nt":
            kernel=ctypes.WinDLL("kernel32")
            kernel.GetConsoleWindow.restype=ctypes.c_void_p
            if not kernel.GetConsoleWindow(): kernel.AllocConsole()
            user=ctypes.WinDLL("user32"); user.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
            user.ShowWindow(kernel.GetConsoleWindow(), 0)
            signal.signal(signal.SIGBREAK, signal.SIG_IGN)
        command=job["command"]
        process=subprocess.Popen(command, cwd=job["cwd"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
        record=process_identity(process.pid) | {"session":job["session"],"profile_id":job["profile_id"],
            "supervisor":process_identity(os.getpid()),"stop_file":job["stop_file"],"port":job["port"]}
        atomic_json(record_path, record)
        if job.get("proxy"):
            from .proxy import CompatibilityProxy
            proxy=CompatibilityProxy(job["proxy_port"],job["port"],job["host"]); proxy.start()
        def read_output():
            for line in iter(process.stdout.readline, b""):
                logger.info(line.decode("utf-8",errors="replace").rstrip())
        reader=threading.Thread(target=read_output,daemon=True); reader.start()
        stop_sent=None
        while process.poll() is None:
            if Path(job["stop_file"]).exists():
                if stop_sent is None:
                    if verify_identity(record):
                        process.send_signal(signal.CTRL_BREAK_EVENT if os.name=="nt" else signal.SIGTERM)
                    stop_sent=time.monotonic()
                elif time.monotonic()-stop_sent > 12 and verify_identity(record): process.kill()
            time.sleep(0.15)
        reader.join(timeout=3)
        atomic_json(record_path, record | {"exit_code":process.returncode,"exited_at":time.time()})
        return process.returncode
    except Exception as exc:
        logger.exception("Supervisor failed")
        existing=read_json(record_path,{})
        if existing.get("session")==job["session"] and verify_identity(existing):
            graceful_break(existing)
            try: psutil.Process(existing["pid"]).wait(timeout=5)
            except psutil.TimeoutExpired:
                if verify_identity(existing): psutil.Process(existing["pid"]).kill()
        atomic_json(record_path, {"session":job["session"],"error":str(exc)})
        return 1
    finally:
        if proxy: proxy.stop()
        Path(job["stop_file"]).unlink(missing_ok=True)
        handler.close()


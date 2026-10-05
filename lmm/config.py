from __future__ import annotations

import json
import copy
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def app_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise ValueError(f"Cannot read {path}. Original file preserved: {error}") from error


@dataclass
class Profile:
    id: str
    name: str
    type: str = "asr"
    model_path: str = ""
    mmproj_path: str = ""
    host: str = "127.0.0.1"
    port: int = 8000
    gpu_layers: int = 999
    parallel: int = 1
    extra_args: list[str] = field(default_factory=list)
    auto_start: bool = False
    requires_mmproj: bool = True
    compatibility_proxy: bool = False
    proxy_port: int = 8001

    def validate(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", self.id):
            raise ValueError("Profile ID must contain only letters, numbers, - and _.")
        if not self.name.strip() or self.type not in {"asr", "llm", "vision"}:
            raise ValueError("A name and a supported model type are required.")
        if not 1 <= self.port <= 65535 or not 1 <= self.proxy_port <= 65535:
            raise ValueError("Ports must be between 1 and 65535.")
        if self.compatibility_proxy and self.port == self.proxy_port:
            raise ValueError("Proxy and model service need different ports.")
        if self.parallel < 1 or self.gpu_layers < -1:
            raise ValueError("Invalid parallel slots or GPU layers.")
        if not self.host or any(c.isspace() for c in self.host) or "," in self.host:
            raise ValueError("Enter one host address.")
        reserved = {"--host", "--port", "-m", "--model", "--mmproj", "-mm", "--models-dir", "--models-preset", "--models-max"}
        if any(str(arg).split("=", 1)[0] in reserved for arg in self.extra_args):
            raise ValueError("Use the dedicated model/host/port fields; router mode is not supported.")
        if not all(isinstance(arg, str) and "\x00" not in arg for arg in self.extra_args):
            raise ValueError("Extra arguments must be a JSON array of strings.")

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        profile = cls(**{key: value for key, value in data.items() if key in cls.__dataclass_fields__})
        profile.validate()
        return profile


DEFAULTS = {
    "language": "zh", "models_dir": "models", "runtime_dir": "runtime/llama.cpp",
    "logs_dir": "logs", "start_with_windows": False, "start_minimized": False,
    "minimize_to_tray": True, "close_to_tray": True, "start_profiles": False,
    "runtime_check": True, "runtime_download": False, "runtime_install": False,
    "models_check": True, "models_auto_update": False,
    "default_host": "127.0.0.1", "default_port": 8000, "default_gpu_layers": 999,
    "app_update_provider": "manifest", "app_update_url": "", "app_check": True,
    "last_checks": {}, "active_profile": "", "tray_hint_shown": False,
}


class Store:
    def __init__(self, root: Path | None = None):
        self.root = (root or app_root()).resolve()
        self.lock = threading.RLock()
        self.config = self.root / "config"
        self.settings = copy.deepcopy(DEFAULTS) | read_json(self.config / "settings.json", {})
        self.profiles = [Profile.from_dict(item) for item in read_json(self.config / "profiles.json", [])]
        for directory in (self.config, self.root / "downloads", self.root / "updates", self.logs, self.models):
            directory.mkdir(parents=True, exist_ok=True)
        self.save()

    def path(self, value: str) -> Path:
        p = Path(os.path.expandvars(value)).expanduser()
        return (p if p.is_absolute() else self.root / p).resolve()

    @property
    def runtime(self) -> Path:
        return self.path(self.settings["runtime_dir"])

    @property
    def models(self) -> Path:
        return self.path(self.settings["models_dir"])

    @property
    def logs(self) -> Path:
        return self.path(self.settings["logs_dir"])

    def relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path.resolve())

    def save(self) -> None:
        with self.lock:
            atomic_json(self.config / "settings.json", self.settings)
            atomic_json(self.config / "profiles.json", [asdict(p) for p in self.profiles])

    def put_profile(self, profile: Profile) -> None:
        profile.validate()
        with self.lock:
            self.profiles = [p for p in self.profiles if p.id != profile.id] + [profile]
            self.save()

    def get_profile(self, profile_id: str) -> Profile:
        return next(p for p in self.profiles if p.id == profile_id)


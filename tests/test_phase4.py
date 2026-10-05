from pathlib import Path
import socket

import pytest

from lmm.config import Profile, Store
from lmm.processes import build_command, port_available, verify_identity


def test_pid_reuse_and_command_identity():
    class Fake:
        def __init__(self, pid): pass
        def is_running(self): return True
        def create_time(self): return 100.0
        def exe(self): return str(Path("server.exe").resolve())
        def cmdline(self): return ["server.exe","--port","8000"]
    record={"pid":123,"create_time":100.0,"executable":str(Path("server.exe").resolve()),"command_line":["server.exe","--port","8000"]}
    assert verify_identity(record, Fake)
    assert not verify_identity(record|{"create_time":200.0},Fake)
    assert not verify_identity(record|{"command_line":["other"]},Fake)
    assert not verify_identity(record|{"executable":"other.exe"},Fake)


def test_bound_port_conflict():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0)); sock.listen()
        assert not port_available("127.0.0.1",sock.getsockname()[1])


def test_command_uses_runtime_capabilities_and_requires_projection(tmp_path):
    store=Store(tmp_path); main=store.models/"model-Q8_0.gguf"; main.write_bytes(b"GGUF")
    p=Profile("asr","ASR",model_path=store.relative(main))
    help_text="--model FILE --mmproj FILE --host HOST --port PORT --gpu-layers N --parallel N --alias NAME --ctx-size N"
    with pytest.raises(ValueError,match="MMProj"): build_command(p,store,help_text)
    projection=store.models/"mmproj-model-Q8_0.gguf"; projection.write_bytes(b"GGUF")
    cmd=build_command(p,store,help_text)
    assert "--gpu-layers" in cmd and "--n-gpu-layers" not in cmd
    assert str(projection) in cmd
    assert "--models-dir" not in cmd

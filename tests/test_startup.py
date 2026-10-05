import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from lmm.windows import Instance


HOST = '''
import json, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QLockFile, QTimer
from lmm.windows import Instance
app = QCoreApplication([])
root = Path(sys.argv[1])
mode = sys.argv[2]
def receive(message):
    if mode == "fail": raise RuntimeError("Window could not be shown")
    (root / "received.json").write_text(json.dumps(message), encoding="utf-8")
if mode == "lock-only":
    lock = QLockFile(str(root / "config" / "manager.lock"))
    assert lock.tryLock(0)
else:
    instance = Instance(root, receive)
    assert instance.primary
    app.aboutToQuit.connect(instance.close)
(root / "ready").touch()
QTimer.singleShot(15000, app.quit)
app.exec()
'''


@pytest.fixture
def host(tmp_path):
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    (tmp_path / "config").mkdir()
    processes = []

    def start(mode="normal"):
        process = subprocess.Popen([sys.executable, "-c", HOST, str(tmp_path), mode],
                                   cwd=Path(__file__).resolve().parents[1],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(process)
        deadline = time.monotonic() + 8
        while not (tmp_path / "ready").exists():
            if process.poll() is not None:
                pytest.fail(process.communicate()[1].decode(errors="replace"))
            assert time.monotonic() < deadline, "Instance host did not start"
            time.sleep(.02)
        return tmp_path

    yield start
    for process in processes:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)


def test_second_launch_confirms_window_action_before_exiting(host):
    root = host()
    instance = Instance(root, lambda _: pytest.fail("Secondary must not receive"))
    assert not instance.primary
    assert json.loads((root / "received.json").read_text()) == {"action": "show"}


def test_locked_instance_without_ipc_does_not_exit_silently(host):
    root = host("lock-only")
    with pytest.raises(RuntimeError, match="无法唤出"):
        Instance(root, lambda _: None, timeout_ms=200)


def test_primary_action_failure_is_reported_to_second_launch(host):
    root = host("fail")
    with pytest.raises(RuntimeError, match="Window could not be shown"):
        Instance(root, lambda _: None)


def test_fragmented_ipc_waits_for_complete_request(host):
    from PySide6.QtNetwork import QLocalSocket
    root = host()
    name = "LocalModelManager-" + hashlib.sha256(str(root).casefold().encode()).hexdigest()[:20]
    socket = QLocalSocket()
    socket.connectToServer(name)
    assert socket.waitForConnected(2000)
    socket.write(b'{"action":'); socket.flush()
    assert not socket.waitForReadyRead(100)
    assert not (root / "received.json").exists()
    socket.write(b'"show"}\n'); socket.flush()
    assert socket.waitForReadyRead(2000)
    assert json.loads(bytes(socket.readLine())) == {"ok": True}
    assert json.loads((root / "received.json").read_text()) == {"action": "show"}
    socket.disconnectFromServer()

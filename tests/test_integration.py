from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading

import httpx
import pytest

from lmm.config import Profile, Store, atomic_json
from lmm.proxy import CompatibilityProxy
from lmm.runtime import Runtime


def test_proxy_preserves_multipart_and_other_json_fields():
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            received.append((self.headers["Content-Type"],self.rfile.read(int(self.headers["Content-Length"]))))
            data=json.dumps({"text":"language Chinese<asr_text> 识别内容。","duration":1.25},ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    upstream=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=upstream.serve_forever,daemon=True); thread.start()
    proxy=CompatibilityProxy(0,upstream.server_port); proxy.start()
    payload=b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n\r\n\x00\xffRAW_AUDIO\r\n--boundary--\r\n'
    try:
        response=httpx.post(f"http://127.0.0.1:{proxy.server.server_port}/v1/audio/transcriptions",content=payload,headers={"Content-Type":"multipart/form-data; boundary=boundary"},trust_env=False)
        assert received==[("multipart/form-data; boundary=boundary",payload)]
        assert response.json()=={"text":" 识别内容。","duration":1.25}
    finally:proxy.stop(); upstream.shutdown(); upstream.server_close()


def test_runtime_interrupted_swap_restores_old_version(tmp_path):
    store=Store(tmp_path); runtime=Runtime(store)
    target=store.runtime; target.mkdir(parents=True); (target/"llama-server.exe").write_text("new")
    backup=target.with_name(".llama-backup-test"); backup.mkdir(); (backup/"llama-server.exe").write_text("old")
    atomic_json(store.config/"runtime_transaction.json",{"target":str(target),"stage":str(target.with_name(".llama-stage-test")),"backup":str(backup),"profiles":[],"state":"prepared"})
    class Manager:
        lock=threading.RLock()
        def start_many(self,ids):assert ids==[]
        def wait_ready_many(self,ids):assert ids==[]
    runtime.recover(Manager())
    assert (target/"llama-server.exe").read_text()=="old"


def test_store_default_mutable_settings_are_isolated(tmp_path):
    first=Store(tmp_path/"a"); second=Store(tmp_path/"b")
    first.settings["last_checks"]["runtime"]=123
    assert not second.settings["last_checks"]


def test_gui_mmproj_pairing_and_ready_id(tmp_path,monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from lmm.gui import Window
    app=QApplication.instance() or QApplication([])
    store=Store(tmp_path); store.put_profile(Profile("qwen","Qwen"))
    window=Window(store)
    metadata={"repo_id":"test/model","revision":"a"*40,"files":[{"filename":"model-Q8_0.gguf","size":10,"is_mmproj":False},{"filename":"mmproj-model-Q8_0.gguf","size":4,"is_mmproj":True}]}
    window.show_repo(metadata); window.repo_table.item(0,0).setCheckState(Qt.CheckState.Checked)
    assert window.repo_table.item(1,0).checkState()==Qt.CheckState.Checked
    window.profile_states["qwen"]={"state":"READY","model_ids":["actual-id"],"models":True,"health":True,"transcription":True}
    window.render_state(); window.copy_model()
    assert QApplication.clipboard().text()=="actual-id"
    window.shutdown(); window.deleteLater(); app.processEvents()

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

from .config import atomic_json, read_json


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "LocalModelManager"


def startup_command(root: Path):
    if getattr(sys, "frozen", False): command=[sys.executable]
    else:
        executable=Path(sys.executable).with_name("pythonw.exe")
        command=[str(executable if executable.exists() else sys.executable),str(Path(__file__).resolve().parents[1]/"main.py")]
    return subprocess.list2cmdline([*command,"--root",str(root.resolve()),"--minimized"])


def set_autostart(enabled: bool, root: Path, registry=None):
    if registry is None:
        import winreg as registry
    with registry.CreateKeyEx(registry.HKEY_CURRENT_USER,RUN_KEY,0,registry.KEY_SET_VALUE | registry.KEY_QUERY_VALUE) as key:
        if enabled: registry.SetValueEx(key,RUN_NAME,0,registry.REG_SZ,startup_command(root))
        else:
            try: registry.DeleteValue(key,RUN_NAME)
            except FileNotFoundError: pass
        try:return registry.QueryValueEx(key,RUN_NAME)[0]
        except FileNotFoundError:return None


class Blob(ctypes.Structure):
    _fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]


def protect(data: bytes, decrypt=False):
    if os.name != "nt": raise RuntimeError("Credential storage requires Windows DPAPI.")
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))); destination=Blob()
    dll=ctypes.WinDLL("crypt32",use_last_error=True)
    function=dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(destination)): raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(destination.data,destination.size)
    finally:
        kernel=ctypes.WinDLL("kernel32"); kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
        kernel.LocalFree(destination.data)


class TokenStore:
    def __init__(self, store):self.path=store.config/"credentials.json"
    def get(self):
        encoded=read_json(self.path,{}).get("hf_token")
        return protect(base64.b64decode(encoded),True).decode() if encoded else ""
    def set(self, token):
        atomic_json(self.path,{"hf_token":base64.b64encode(protect(token.encode())).decode()} if token else {})


def show_window(window):
    window.showNormal()
    if os.name == "nt":
        # A hidden launcher can suppress Qt's first native ShowWindow call even
        # though QWidget.isVisible() is already true. Explicitly restore the HWND.
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.ShowWindow(int(window.winId()), 9)  # SW_RESTORE
    window.raise_()
    window.activateWindow()


class Instance:
    def __init__(self, root, receive, message=None, timeout_ms=5000):
        from PySide6.QtCore import QLockFile, QTimer
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        root = Path(root).resolve()
        name="LocalModelManager-"+hashlib.sha256(str(root).casefold().encode()).hexdigest()[:20]
        self.lock=QLockFile(str(root/"config"/"manager.lock"))
        self.primary=self.lock.tryLock(0)
        self.server=None
        if self.primary:
            QLocalServer.removeServer(name)
            self.server=QLocalServer(); self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
            if not self.server.listen(name):
                self.lock.unlock()
                raise RuntimeError("无法创建管理器的窗口唤出通道：" + self.server.errorString())
            def connected():
                while self.server.hasPendingConnections():
                    socket=self.server.nextPendingConnection()
                    buffer=bytearray()
                    timer=QTimer(socket); timer.setSingleShot(True)
                    timer.timeout.connect(socket.disconnectFromServer); timer.start(timeout_ms)
                    socket.disconnected.connect(socket.deleteLater)
                    def read(socket=socket, buffer=buffer, timer=timer):
                        buffer.extend(bytes(socket.readAll()))
                        if len(buffer)>4096:
                            socket.disconnectFromServer(); return
                        if b"\n" not in buffer:return
                        timer.stop()
                        try:
                            payload=json.loads(buffer)
                            if not isinstance(payload,dict):raise ValueError("Invalid instance request")
                            receive(payload)
                            reply={"ok":True}
                            logging.getLogger("lmm").info("Instance action handled: %s",payload.get("action","show"))
                        except Exception as exc:
                            logging.getLogger("lmm").exception("Instance action failed")
                            reply={"ok":False,"error":str(exc)}
                        socket.write(json.dumps(reply).encode()+b"\n")
                        socket.disconnectFromServer()
                    socket.readyRead.connect(read)
                    if socket.bytesAvailable():read()
            self.server.newConnection.connect(connected)
        else:
            if self.lock.error()!=QLockFile.LockError.LockFailedError:
                raise RuntimeError("无法访问管理器的运行锁，请检查 config 文件夹的写入权限。")
            socket=QLocalSocket(); socket.connectToServer(name)
            try:
                if not socket.waitForConnected(timeout_ms):
                    raise RuntimeError("已有管理器实例，但无法唤出它的窗口。请退出其他 Windows 账户或后台测试环境中的管理器后重试。\n" + socket.errorString())
                socket.write(json.dumps(message or {"action":"show"}).encode()+b"\n")
                socket.flush()
                deadline=time.monotonic()+timeout_ms/1000
                while not socket.canReadLine():
                    remaining=round((deadline-time.monotonic())*1000)
                    if remaining<=0 or not socket.waitForReadyRead(remaining):
                        raise RuntimeError("已联系到运行中的管理器，但窗口未响应。请从托盘退出管理器后重试。")
                reply=json.loads(bytes(socket.readLine()))
                if not reply.get("ok"):
                    raise RuntimeError("管理器未能打开窗口："+str(reply.get("error","Unknown error")))
            finally:socket.disconnectFromServer()

    def close(self):
        if self.server:self.server.close()
        if self.primary:self.lock.unlock()

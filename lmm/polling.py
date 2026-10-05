from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal


class Poller(QObject):
    result=Signal(str,object)
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix="monitor")
        self.pending=set(); self.callback=callback
        self.result.connect(self.received)
    def request(self,key,function):
        if key in self.pending:return
        self.pending.add(key)
        def run():
            try:value=function()
            except Exception as exc:value={"error":str(exc)}
            self.result.emit(key,value)
        self.pool.submit(run)
    def received(self,key,value):
        self.pending.discard(key); self.callback(key,value)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot


class Interrupted(Exception):
    pass


@dataclass
class Control:
    event: threading.Event = field(default_factory=threading.Event)
    paused: bool = False

    def check(self):
        if self.event.is_set():
            raise Interrupted("Paused" if self.paused else "Cancelled")

    def wait(self, seconds: float):
        self.event.wait(seconds)
        self.check()


class Jobs(QObject):
    changed = Signal(str, dict)
    completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lmm")
        self.items: dict[str, dict] = {}
        self.callbacks = {}
        self.completed.connect(self._completed)
        self.failed.connect(self._failed)
        self.changed.connect(self._changed)

    def submit(self, title: str, function: Callable, done: Callable | None = None, error: Callable | None = None, resumable=False) -> str:
        key = uuid.uuid4().hex
        self.items[key] = {"title": title, "state": "Queued", "control": Control(), "function": function, "resumable": resumable}
        self.callbacks[key] = (done, error)
        self._run(key)
        return key

    def _run(self, key: str):
        item = self.items[key]
        item["control"] = control = Control()
        item["state"] = "Running"
        def execute():
            try:
                result = item["function"](control, lambda info: self.changed.emit(key, info))
                control.check()
                self.completed.emit(key, result)
            except Interrupted as exc:
                self.changed.emit(key, {"state": str(exc)})
            except Exception as exc:
                logging.getLogger("lmm").exception("Task failed: %s", item["title"])
                self.failed.emit(key, str(exc))
        self.pool.submit(execute)

    def pause(self, key):
        item = self.items[key]
        if item["state"] == "Running" and item["resumable"]:
            item["control"].paused = True
            item["control"].event.set()
            item["state"] = "Pausing"

    def cancel(self, key):
        item = self.items[key]
        item["control"].paused = False
        item["control"].event.set()

    def resume(self, key):
        if self.items[key]["state"] in {"Paused", "Failed", "Cancelled"} and self.items[key]["resumable"]:
            self._run(key)

    @Slot(str, dict)
    def _changed(self, key, info):
        self.items[key].update(info)

    @Slot(str, object)
    def _completed(self, key, result):
        self.items[key]["state"] = "Completed"
        callback = self.callbacks[key][0]
        if callback:
            try:
                callback(result)
            except Exception:
                logging.getLogger("lmm").exception("Completion handler failed")

    @Slot(str, str)
    def _failed(self, key, error):
        self.items[key].update(state="Failed", error=error)
        callback = self.callbacks[key][1]
        if callback:
            callback(error)


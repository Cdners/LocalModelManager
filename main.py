from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--supervise", type=Path)
    parser.add_argument("--apply-update",type=Path)
    parser.add_argument("--update-ack",type=Path)
    parser.add_argument("--setup-qwen",action="store_true")
    parser.add_argument("--record-seconds",type=float)
    parser.add_argument("--test-audio",type=Path)
    parser.add_argument("--screenshot",type=Path)
    options = parser.parse_args()
    if options.supervise:
        from lmm.processes import supervise
        return supervise(options.supervise)
    if options.apply_update:
        from lmm.updater import apply_job
        return apply_job(options.apply_update)
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from lmm.i18n import MessageBox as QMessageBox, set_language
    from lmm.config import Store
    from lmm.windows import Instance
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("LocalModelManager")
    app.setQuitOnLastWindowClosed(False)
    try:
        store = Store(options.root)
        set_language(store.settings["language"])
        handler = RotatingFileHandler(store.logs / "app.log", maxBytes=20 * 1024**2, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger("lmm").addHandler(handler); logging.getLogger("lmm").setLevel(logging.INFO)
        message={"action":"setup"} if options.setup_qwen else {"action":"record","seconds":options.record_seconds} if options.record_seconds else {"action":"test-audio","path":str(options.test_audio)} if options.test_audio else {"action":"show"}
        instance=Instance(store.root,lambda incoming:window.external_action(incoming),message)
        if not instance.primary:
            return 0
        from lmm.gui import Window
        window = Window(store)
        window.activate()
        app.aboutToQuit.connect(window.shutdown); app.aboutToQuit.connect(instance.close)
        if not (options.minimized or store.settings["start_minimized"]) or not window.tray.icon.isVisible():window.tray.show_window()
        if options.setup_qwen or options.record_seconds or options.test_audio:QTimer.singleShot(800,lambda:window.external_action(message))
        if options.update_ack:
            from lmm.updater import acknowledge
            ids=acknowledge(options.update_ack,store)
            for identity in ids:QTimer.singleShot(1000,lambda p=identity:window.service("start",p))
        if options.screenshot:
            def capture():
                options.screenshot.parent.mkdir(parents=True,exist_ok=True); window.grab().save(str(options.screenshot))
            QTimer.singleShot(2500,capture)
        if options.smoke:
            QTimer.singleShot(3000, app.quit)
        return app.exec()
    except Exception as exc:
        logging.getLogger("lmm").exception("Application startup failed")
        QMessageBox.critical(None, "Local Model Manager", str(exc))
        return 1


if __name__ == "__main__":
    try:
        result=main()
    except Exception:
        import traceback
        destination=(Path(sys.executable).parent if getattr(sys,"frozen",False) else Path(__file__).parent)/"logs"
        destination.mkdir(parents=True,exist_ok=True)
        (destination/"startup-error.log").write_text(traceback.format_exc(),encoding="utf-8")
        result=1
    raise SystemExit(result)


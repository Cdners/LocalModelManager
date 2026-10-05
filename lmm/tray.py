from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .windows import show_window
from .i18n import MessageBox as QMessageBox, bind, tr


class Tray(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window=window; self.quitting=False
        self.icon=QSystemTrayIcon(window.windowIcon(),self)
        self.icon.setToolTip("Local Model Manager")
        self.menu=QMenu(window); self.menu.aboutToShow.connect(self.build_menu)
        self.icon.setContextMenu(self.menu); self.icon.activated.connect(self.activated)
        if QSystemTrayIcon.isSystemTrayAvailable():self.icon.show()
        window.installEventFilter(self)

    def activated(self, reason):
        if reason==QSystemTrayIcon.ActivationReason.DoubleClick:self.show_window()

    def show_window(self):
        show_window(self.window)

    def build_menu(self):
        self.menu.clear()
        self.menu.addAction(tr("Open Local Model Manager"),self.show_window); self.menu.addSeparator()
        for profile in self.window.store.profiles:
            group=self.menu.addMenu(profile.name)
            for verb in ("Start","Stop","Restart"):
                group.addAction(tr(verb),lambda p=profile.id,v=verb:self.window.service(v.lower(),p))
        self.menu.addSeparator()
        gpu=getattr(self.window,"gpu_state",{})
        self.menu.addAction("GPU: "+gpu.get("name",tr("Unavailable"))).setEnabled(False)
        if gpu.get("used") is not None and gpu.get("total"):
            self.menu.addAction(tr("VRAM")+f": {gpu['used']/1024**3:.1f} / {gpu['total']/1024**3:.1f} GiB").setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction(tr("Start all auto-start profiles"),self.window.start_auto_profiles)
        self.menu.addAction(tr("Stop all managed models"),self.window.stop_all)
        self.menu.addSeparator(); self.menu.addAction(tr("Exit"),self.request_exit)

    def hide_window(self):
        self.window.hide()
        if not self.window.store.settings["tray_hint_shown"]:
            self.icon.showMessage("Local Model Manager",tr("Local Model Manager is still running in the background."),QSystemTrayIcon.MessageIcon.Information,5000)
            self.window.store.settings["tray_hint_shown"]=True; self.window.store.save()

    def eventFilter(self, obj, event):
        if obj is self.window and not self.quitting:
            if event.type()==QEvent.Type.Close:
                event.ignore()
                if self.window.store.settings["close_to_tray"] and self.icon.isVisible():self.hide_window()
                else:self.request_exit()
                return True
            if event.type()==QEvent.Type.WindowStateChange and self.window.isMinimized():
                if self.window.store.settings["minimize_to_tray"] and self.icon.isVisible():QTimer.singleShot(0,self.hide_window)
        return False

    def request_exit(self):
        if self.quitting:return
        self.window.jobs.submit("Checking running services",lambda c,p:[x.id for x in self.window.store.profiles if self.window.manager.is_running(x.id)],self.choose_exit,self.window.error)

    def choose_exit(self, running):
        if not running:self.finish(); return
        box=QMessageBox(self.window); box.setWindowTitle(tr("Exit Local Model Manager"))
        bind(box,"Managed model services are still running.")
        keep=box.addButton(tr("Keep services and exit"),QMessageBox.ButtonRole.AcceptRole)
        stop=box.addButton(tr("Stop services and exit"),QMessageBox.ButtonRole.DestructiveRole)
        cancel=box.addButton(tr("Cancel"),QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel); box.setEscapeButton(cancel); box.exec()
        if box.clickedButton() is keep:self.finish()
        elif box.clickedButton() is stop:
            self.window.jobs.submit("Stop services and exit",lambda c,p:self.window.manager.stop_all(),lambda _:self.finish(),self.window.error)

    def finish(self):
        self.quitting=True; self.icon.hide()
        for item in self.window.jobs.items.values():item["control"].event.set()
        self.window.hide(); QApplication.instance().quit()

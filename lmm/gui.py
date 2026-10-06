from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from . import __version__
from .config import Store
from .i18n import MessageBox as QMessageBox, bind, retranslate, set_language, tr
from .jobs import Jobs
from .workspace import ApplicationPages, label, buttons


PAGES = [
    ('Dashboard', 'Overview', 'Manage services, monitor your GPU, and connect your apps.'),
    ('Models', 'Model library', 'Import models and choose a compatible runtime.'),
    ('Downloads', 'Downloads', 'Track transfers and resume unfinished downloads.'),
    ('Runtime', 'Runtime', 'Manage independent inference engines.'),
    ('OpenTypeless', 'Voice input', 'Connect OpenTypeless and test local speech recognition.'),
    ('Logs', 'Logs', 'Inspect application and model service output.'),
    ('Settings', 'Settings', 'Make this workspace your own.'),
]


def icon() -> QIcon:
    pixmap = QPixmap(128, 128); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#087f72')); painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 120, 120, 32, 32)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('white'), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawPolyline(QPolygonF([QPointF(32, 44), QPointF(32, 84), QPointF(49, 84)]))
    painter.drawPolyline(QPolygonF([QPointF(66, 84), QPointF(66, 44), QPointF(81, 66), QPointF(96, 44), QPointF(96, 84)]))
    painter.end()
    return QIcon(pixmap)


def nav_icon(index):
    pixmap = QPixmap(48, 48); pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#607687'), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if index == 0:
        for x in (4, 14):
            for y in (4, 14): painter.drawRoundedRect(x, y, 6, 6, 1, 1)
    elif index == 1:
        painter.drawPolygon(QPolygonF([QPointF(3, 8), QPointF(12, 3), QPointF(21, 8), QPointF(12, 13)]))
        for y in (12, 16): painter.drawPolyline(QPolygonF([QPointF(3, y), QPointF(12, y+5), QPointF(21, y)]))
    elif index == 2:
        painter.drawLine(12, 3, 12, 15); painter.drawLine(7, 10, 12, 15); painter.drawLine(17, 10, 12, 15)
        painter.drawPolyline(QPolygonF([QPointF(4, 16), QPointF(4, 20), QPointF(20, 20), QPointF(20, 16)]))
    elif index == 3:
        painter.drawRoundedRect(6, 6, 12, 12, 2, 2); painter.drawRect(9, 9, 6, 6)
        for n in (9, 15):
            painter.drawLine(n, 3, n, 6); painter.drawLine(n, 18, n, 21)
            painter.drawLine(3, n, 6, n); painter.drawLine(18, n, 21, n)
    elif index == 4:
        for x, height in ((4, 6), (8, 12), (12, 18), (16, 10), (20, 4)):
            painter.drawLine(x, 12-height//2, x, 12+height//2)
    elif index == 5:
        painter.drawRoundedRect(5, 3, 14, 18, 2, 2)
        for y in (8, 12, 16): painter.drawLine(9, y, 15, y)
    else:
        for y, x in ((6, 9), (12, 16), (18, 7)):
            painter.drawLine(3, y, 21, y); painter.setBrush(QColor('#f8fafb')); painter.drawEllipse(QPointF(x, y), 2, 2)
    painter.end(); return QIcon(pixmap)


STYLE = '''
QWidget { color: #233445; font-family: '__FONT__'; font-size: 13px; }
QMainWindow, QDialog, QWidget#page { background: #f4f6f9; }
QFrame#sidebar { background: #fcfdfd; border-right: 1px solid #e2e8ed; }
QLabel { background: transparent; }
QLabel#brand { font-size: 15px; font-weight: 650; color: #213e47; }
QLabel#eyebrow { color: #8a99a5; font-size: 10px; font-weight: 650; letter-spacing: 1px; }
QLabel#title { font-size: 27px; font-weight: 650; color: #172d3a; }
QLabel#section { font-size: 16px; font-weight: 650; color: #213744; }
QLabel#subtitle { color: #728392; font-size: 12px; }
QLabel#metric { font-size: 23px; font-weight: 650; color: #223f4d; }
QLabel#code { font-family: 'Cascadia Code', 'Consolas'; font-size: 13px; color: #355365; }
QListWidget#nav { background: transparent; border: none; outline: 0; padding: 0; }
QListWidget#nav::item { padding: 12px 10px; margin: 3px 0; border-radius: 8px; color: #657b89; }
QListWidget#nav::item:hover { background: #f0f4f5; }
QListWidget#nav::item:selected { background: #e5f2ee; color: #087769; font-weight: 650; }
QFrame#card { background: #ffffff; border: 1px solid #e0e7ed; border-radius: 12px; }
QPushButton { background: #ffffff; border: 1px solid #d8e1e7; border-radius: 7px; padding: 8px 13px; min-height: 18px; }
QPushButton:hover { background: #f2f8f6; border-color: #9dbfb6; color: #087769; }
QPushButton:pressed { background: #e4f0ec; }
QPushButton:focus { border: 1px solid #087f72; }
QPushButton:disabled { color: #a3b0b9; background: #f5f7f9; border-color: #e6ebef; }
QPushButton[primary="true"] { background: #087f72; color: white; border-color: #087f72; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #066c62; }
QPushButton[primary="true"]:disabled { background: #dbe9e5; color: #8ea89e; border-color: #dbe9e5; }
QPushButton[quiet="true"] { background: transparent; border: none; color: #68808c; padding: 5px 7px; }
QPushButton[quiet="true"]:hover { background: #edf4f1; color: #087769; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { background: #ffffff; border: 1px solid #d9e2e9; border-radius: 7px; padding: 8px; selection-background-color: #d7eee6; selection-color: #174e43; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border-color: #55a396; }
QLineEdit:read-only { background: #f7f9fa; }
QComboBox { min-height: 20px; padding-right: 24px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url("__ASSETS__/chevron-down.svg"); width: 12px; height: 8px; }
QSpinBox { padding-right: 22px; }
QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; border: none; }
QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; border: none; }
QSpinBox::up-arrow { image: url("__ASSETS__/chevron-up.svg"); width: 10px; height: 7px; }
QSpinBox::down-arrow { image: url("__ASSETS__/chevron-down.svg"); width: 10px; height: 7px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e5f2ee; selection-color: #087769; outline: 0; padding: 4px; }
QCheckBox { spacing: 10px; min-height: 25px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QTableWidget { background: #ffffff; alternate-background-color: #f8fafb; gridline-color: #edf1f4; border: 1px solid #e0e7ed; border-radius: 8px; selection-background-color: #e1f2eb; selection-color: #18584b; }
QTableWidget::item { padding: 6px 8px; border: none; }
QHeaderView::section { background: #f0f4f6; color: #6a7c88; padding: 10px 8px; border: none; border-bottom: 1px solid #e0e7ed; font-size: 12px; font-weight: 600; }
QProgressBar { border: none; background: #e9eff2; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #23a184; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #ccd6dc; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { padding: 11px 18px; margin-right: 6px; margin-bottom: 12px; border-radius: 7px; color: #728592; }
QTabBar::tab:selected { background: #e5f2ee; color: #087769; font-weight: 600; }
QTabBar::tab:hover { background: #eef3f4; }
QStatusBar { background: #fcfdfd; border-top: 1px solid #e2e8ed; color: #82929d; font-size: 11px; }
QStatusBar::item { border: none; }
QMenu { background: white; padding: 6px; border: 1px solid #dce5e9; }
QMenu::item { padding: 8px 24px; border-radius: 5px; }
QMenu::item:selected { background: #e5f2ee; color: #087769; }
QToolTip { background: #203c45; color: white; border: none; padding: 6px; }
'''.replace('__ASSETS__', (Path(__file__).resolve().parents[1] / 'assets').as_posix())


class Window(ApplicationPages, QMainWindow):
    def __init__(self, store: Store):
        super().__init__(); self.store = store
        set_language(store.settings['language'])
        self.jobs = Jobs(self)
        self.setWindowTitle(f'Local Model Manager · {__version__}'); self.setWindowIcon(icon())
        self.resize(1240, 860); self.setMinimumSize(1020, 720)
        self.apply_style()
        shell = QWidget(); layout = QHBoxLayout(shell); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar); side.setContentsMargins(20, 26, 20, 20); side.setSpacing(18)
        brand = QHBoxLayout(); brand.setSpacing(10)
        mark = QLabel(); mark.setPixmap(icon().pixmap(38, 38)); brand.addWidget(mark)
        brand.addWidget(label('Local Model\nManager', 'brand')); brand.addStretch(); side.addLayout(brand)
        side.addSpacing(10); side.addWidget(label('LOCAL WORKSPACE', 'eyebrow'))
        self.nav = QListWidget(); self.nav.setObjectName('nav'); self.nav.setIconSize(QSize(20, 20)); self.nav.setSpacing(1)
        side.addWidget(self.nav, 1)
        side.addWidget(label('Your models. On your machine.', 'subtitle'))
        side.addWidget(label('v' + __version__, 'subtitle'))
        self.stack = QStackedWidget(); layout.addWidget(sidebar); layout.addWidget(self.stack, 1); self.setCentralWidget(shell)
        self.pages = {}
        for index, (name, title, description) in enumerate(PAGES):
            self.nav.addItem(QListWidgetItem(nav_icon(index), tr(title)))
            page = QWidget(); page.setObjectName('page'); content = QVBoxLayout(page)
            content.setContentsMargins(30, 28, 30, 24); content.setSpacing(18)
            header = QVBoxLayout(); header.setSpacing(6)
            header.addWidget(label(title, 'title')); header.addWidget(label(description, 'subtitle')); content.addLayout(header)
            self.pages[name] = content
            if name == 'Settings': self.stack.addWidget(page)
            else:
                scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(page)
                self.stack.addWidget(scroll)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0)
        self.settings_fields = {}; self.build_settings(); self.build_workspace()
        self.statusBar().showMessage(tr('Ready · Your workspace is stored beside the application'))

    def error(self, message):
        QMessageBox.warning(self, 'Local Model Manager', str(message))

    def apply_style(self):
        family = 'Microsoft YaHei UI' if self.store.settings['language'] == 'zh' else 'Segoe UI'
        self.setStyleSheet(STYLE.replace('__FONT__', family))

    def settings_card(self, parent, title):
        box = self.card(parent); box.addWidget(label(title, 'section')); return box

    def build_settings(self):
        self.settings_tabs = QTabWidget(); self.settings_tabs.setDocumentMode(True)
        self.settings_tab_names = ['General', 'Storage & services', 'Updates & access']
        layouts = []
        for name in self.settings_tab_names:
            page = QWidget(); page.setObjectName('page'); content = QVBoxLayout(page); content.setContentsMargins(0, 2, 8, 8); content.setSpacing(16)
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
            self.settings_tabs.addTab(scroll, tr(name).replace('&', '&&')); layouts.append(content)
        self.pages['Settings'].addWidget(self.settings_tabs, 1)
        general, storage, updates = layouts
        appearance = self.settings_card(general, 'Appearance & language')
        startup = self.settings_card(general, 'Startup & window')
        folders = self.settings_card(storage, 'Storage')
        defaults = self.settings_card(storage, 'Service defaults')
        automatic = self.settings_card(updates, 'Automatic updates')
        self.app_settings_box = self.settings_card(updates, 'Software updates')
        self.access_settings_box = self.settings_card(updates, 'Hugging Face access')
        specs = [
            (appearance, 'language', 'Language', [('中文（简体）', 'zh'), ('English', 'en')]),
            (startup, 'start_with_windows', 'Run at Windows sign-in', bool),
            (startup, 'start_minimized', 'Start in the system tray', bool),
            (startup, 'start_profiles', 'Start enabled model profiles', bool),
            (startup, 'minimize_to_tray', 'Minimize to tray', bool),
            (startup, 'close_to_tray', 'Close to tray', bool),
            (folders, 'models_dir', 'Models folder', str),
            (folders, 'runtime_dir', 'Runtime folder', str),
            (folders, 'logs_dir', 'Logs folder', str),
            (defaults, 'default_host', 'Host', str),
            (defaults, 'default_port', 'Port', int),
            (defaults, 'default_gpu_layers', 'GPU layers', int),
            (automatic, 'runtime_check', 'Check runtime daily', bool),
            (automatic, 'runtime_download', 'Download runtime updates', bool),
            (automatic, 'runtime_install', 'Install runtime updates (restart & rollback)', bool),
            (automatic, 'models_check', 'Check models daily', bool),
            (automatic, 'models_auto_update', 'Download and switch model updates', bool),
            (automatic, 'app_check', 'Check app updates daily', bool),
            (self.app_settings_box, 'app_update_provider', 'Update provider', [('JSON manifest', 'manifest'), ('GitHub Releases', 'github')]),
            (self.app_settings_box, 'app_update_url', 'Manifest URL / GitHub repository', str),
        ]
        for box, key, title, kind in specs:
            value = self.store.settings[key]
            if kind is bool:
                widget = bind(QCheckBox(), title); widget.setChecked(value); box.addWidget(widget)
            else:
                if kind is int:
                    widget = QSpinBox(); widget.setRange(0, 65535); widget.setValue(value)
                elif isinstance(kind, list):
                    widget = QComboBox()
                    for text, data in kind: widget.addItem(tr(text), data)
                    widget.setCurrentIndex(widget.findData(value))
                else: widget = QLineEdit(str(value))
                form = QFormLayout(); form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                caption = label(title); caption.setMinimumWidth(130); form.addRow(caption, widget); box.addLayout(form)
            self.settings_fields[key] = widget
        appearance.addWidget(label('Changes to language take effect immediately.', 'subtitle'))
        for content in layouts: content.addStretch()
        footer = QHBoxLayout(); footer.addStretch()
        self.save_button = bind(QPushButton(), 'Save settings'); self.save_button.setProperty('primary', True)
        self.save_button.clicked.connect(self.save_settings); footer.addWidget(self.save_button); self.pages['Settings'].addLayout(footer)
        self.settings_fields['language'].currentIndexChanged.connect(self.change_language)

    def change_language(self, *_):
        language = self.settings_fields['language'].currentData()
        set_language(language); self.store.settings['language'] = language; self.store.save()
        self.apply_style()
        retranslate(self)
        for index, (_, title, _) in enumerate(PAGES): self.nav.item(index).setText(tr(title))
        for index, title in enumerate(self.settings_tab_names): self.settings_tabs.setTabText(index, tr(title).replace('&', '&&'))
        provider = self.settings_fields['app_update_provider']
        provider.setItemText(0, tr('JSON manifest')); provider.setItemText(1, tr('GitHub Releases'))
        self.log_source.setItemText(0, tr('All services')); self.log_source.setItemText(1, tr('Application'))
        self.mic_combo.setItemText(0, tr('Windows default microphone'))
        if self.last_metadata:
            for row, item in enumerate(self.last_metadata['files']):
                self.repo_table.item(row, 3).setText('MMProj' if item['is_mmproj'] else tr('Model'))
            self.repo_note.setText(self.compatibility_text(self.last_metadata))
        self.refresh_installed(); self.refresh_downloads(); self.refresh_runtime(); self.refresh_app_update(); self.render_state()
        if hasattr(self, 'network_editor'): self.network_editor.refresh_language()
        self.refresh_profiles()
        for i, title in enumerate(('Use global proxy','Direct','Custom proxy')): self.task_proxy.setItemText(i,tr(title))
        from .adapters import adapters
        for i, adapter in enumerate(adapters().values()): self.runtime_selector.setItemText(i,adapter.name + ('' if adapter.implemented else ' · '+tr('Reserved')))
        if self.gpu_state: self.polled('gpu', self.gpu_state)
        self.statusBar().showMessage(tr('Settings saved'))
        if hasattr(self, 'tray'): self.tray.build_menu()

    def save_settings(self):
        try:
            updated = {}
            for key, widget in self.settings_fields.items():
                if isinstance(widget, QCheckBox): value = widget.isChecked()
                elif isinstance(widget, QSpinBox): value = widget.value()
                elif isinstance(widget, QComboBox): value = widget.currentData()
                else: value = widget.text().strip()
                updated[key] = value
            if not all(updated[k] for k in ('models_dir', 'runtime_dir', 'logs_dir', 'default_host')):
                raise ValueError(tr('Folders and host cannot be empty.'))
            if updated['default_host'] not in {'127.0.0.1', 'localhost', '::1'}:
                if QMessageBox.warning(self, 'Network access', 'A non-loopback host exposes the API to other devices. The app will not configure your firewall. Continue?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
            self.settings_guard(updated)
            self.store.settings.update(updated); self.store.save()
            self.statusBar().showMessage(tr('Settings saved'))
        except Exception as exc: self.error(exc)

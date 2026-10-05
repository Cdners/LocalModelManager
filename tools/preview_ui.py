"""Render both UI languages in an isolated workspace using read-only local service data."""
from pathlib import Path
import json
import os
import sys
import uuid

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QCheckBox
from lmm import __version__
from lmm.api import snapshot
from lmm.config import Profile, Store, read_json, atomic_json
from lmm.dialogs import ProfileDialog
from lmm.gpu import Monitor
from lmm.gui import Window, PAGES
from lmm.i18n import ZH


project = Path(__file__).resolve().parents[1]
live = project / 'dist' / 'LocalModelManager'
output = project / 'artifacts' / ('ui-' + __version__)
output.mkdir(parents=True, exist_ok=True)
store = Store(output / ('workspace-' + uuid.uuid4().hex[:8]))
store.settings['runtime_dir'] = str(live / 'runtime' / 'llama.cpp')
store.profiles = [Profile.from_dict(item) for item in read_json(live / 'config' / 'profiles.json', [])]
store.save()
models = read_json(live / 'config' / 'models.json', [])
atomic_json(store.config / 'models.json', [{**r, 'path': str(live / r['path'])} for r in models])
app = QApplication([]); app.setStyle('Fusion')
# The offscreen Windows plugin has no system font discovery. Register local
# fonts for faithful previews; the shipped Windows platform plugin finds them.
for name in ('segoeui.ttf', 'seguisb.ttf', 'msyh.ttc', 'msyhbd.ttc', 'consola.ttf', 'seguisym.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['SystemRoot']) / 'Fonts' / name))
window = Window(store)
window.runtime_latest = read_json(live / 'config' / 'runtime_latest.json', {})
window.refresh_runtime()
window.polled('gpu', Monitor().sample())
for profile in store.profiles:
    state = snapshot(profile)
    record = read_json(live / 'config' / 'processes' / (profile.id + '.json'), {})
    window.profile_states[profile.id] = state | {'pid': record.get('pid', '—')}
window.render_state()
window.show()
report = {'version': __version__, 'preview_only': True, 'screenshots': [], 'horizontal_overflow': [], 'untranslated_bindings': []}
neutral = {'Local Model\nManager', 'Qwen3-ASR-1.7B', 'MMProj', '—', 'v' + __version__}
for language_index, language in enumerate(('zh', 'en')):
    window.settings_fields['language'].setCurrentIndex(language_index)
    for dimensions in [(1240, 860), (1020, 720)]:
        window.resize(*dimensions)
        for index, (key, _, _) in enumerate(PAGES):
            window.nav.setCurrentRow(index); app.processEvents(); app.processEvents()
            path = output / f'{language}-{key}-{dimensions[0]}.png'
            window.grab().save(str(path)); report['screenshots'].append(str(path))
            if key != 'Settings':
                scroll = window.stack.widget(index)
                if scroll.horizontalScrollBar().maximum() > 0: report['horizontal_overflow'].append(path.name)
        if dimensions[0] == 1240:
            for tab in (1, 2):
                window.settings_tabs.setCurrentIndex(tab); app.processEvents()
                path = output / f'{language}-Settings-tab{tab}.png'; window.grab().save(str(path)); report['screenshots'].append(str(path))
            window.settings_tabs.setCurrentIndex(0)
    for child in [window, *window.findChildren(QLabel), *window.findChildren(QPushButton), *window.findChildren(QCheckBox)]:
        for source, _ in getattr(child, '_translations', {}).values():
            if source not in ZH and source not in neutral and not source.startswith('NVIDIA'):
                report['untranslated_bindings'].append(source)
    if store.profiles:
        dialog = ProfileDialog(store, store.profiles[0], window)
        dialog.show(); app.processEvents()
        dialog.grab().save(str(output / f'{language}-profile.png')); dialog.hide(); dialog.deleteLater()
    # A contact sheet for visual inspection; individual captures keep full resolution.
    sheet = QPixmap(1240, 4 * 430); sheet.fill(QColor('#e1e7eb'))
    painter = QPainter(sheet)
    for index, (key, _, _) in enumerate(PAGES):
        pixmap = QPixmap(str(output / f'{language}-{key}-1240.png'))
        painter.drawPixmap((index % 2) * 620, (index // 2) * 430, pixmap.scaled(620, 430, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    painter.end(); sheet.save(str(output / f'{language}-overview.png'))
window.hide(); window.shutdown()
report['untranslated_bindings'] = sorted(set(report['untranslated_bindings']))
atomic_json(output / 'report.json', report)
print(json.dumps({'output': str(output), 'horizontal_overflow': report['horizontal_overflow'], 'untranslated_bindings': report['untranslated_bindings']}, ensure_ascii=False))

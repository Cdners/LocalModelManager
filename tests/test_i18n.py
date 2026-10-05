import re
from string import Formatter

from lmm.config import Profile, Store
from lmm.i18n import ZH, set_language, tr


def test_translation_placeholders_match():
    def fields(text):
        return {field for _, field, _, _ in Formatter().parse(text) if field}
    for source, translated in ZH.items():
        assert fields(source) == fields(translated), source
        assert not re.search('[\u4e00-\u9fff]', source), source


def test_live_language_switch_preserves_user_data_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QCheckBox
    from lmm.gui import Window
    from lmm.tray import Tray
    from lmm.dialogs import ProfileDialog
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path)
    profile = Profile('qwen-user-id', '我的模型', model_path='models/中文 model.gguf')
    store.put_profile(profile)
    window = Window(store); window.tray = Tray(window)
    window.profile_states[profile.id] = {'state': 'READY', 'model_ids': ['actual-api-id'], 'health': True, 'models': True, 'transcription': True}
    window.render_state()
    window.transcript.setPlainText('保留原文。Keep this transcript.')
    window.raw_response.setPlainText('{"text":"原始结果"}')
    window.settings_fields['default_host'].setText('localhost')  # Unsaved edit
    window.show_repo({'revision': 'a'*40, 'files': [{'filename': 'model-Q8_0.gguf', 'size': 10, 'is_mmproj': False}, {'filename': 'mmproj-model-Q8_0.gguf', 'size': 4, 'is_mmproj': True}]})
    window.repo_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    record = window.downloads.add('model', 'Download models', {})
    window.downloads.update(record['id'], {'state': 'Paused'})
    assert window.nav.item(0).text() == '概览'
    assert '已就绪' in window.state_label.text()
    jobs = window.jobs
    window.settings_fields['language'].setCurrentIndex(1)
    app.processEvents()
    assert window.nav.item(0).text() == 'Overview'
    assert window.save_button.text() == 'Save settings'
    assert 'READY' in window.state_label.text()
    assert window.download_table.item(0, 1).text() == 'Paused'
    assert Store(tmp_path).settings['language'] == 'en'
    assert window.jobs is jobs and window.profile_states[profile.id]['state'] == 'READY'
    assert window.repo_table.item(0, 0).checkState() == Qt.CheckState.Checked
    assert window.repo_table.item(1, 0).checkState() == Qt.CheckState.Checked
    assert window.repo_table.item(0, 3).text() == 'Model'
    assert window.profile_combo.currentData() == profile.id
    assert window.settings_fields['default_host'].text() == 'localhost'
    assert window.transcript.toPlainText() == '保留原文。Keep this transcript.'
    assert window.raw_response.toPlainText() == '{"text":"原始结果"}'
    for kind in (QLabel, QPushButton, QCheckBox):
        for widget in window.findChildren(kind):
            assert not re.search('[\u4e00-\u9fff]', widget.text()), widget.text()
    window.tray.build_menu()
    assert window.tray.menu.actions()[0].text() == 'Open Local Model Manager'
    dialog = ProfileDialog(store, profile, window)
    assert dialog.values['type'].currentData() == 'asr'
    dialog.accept_profile()
    assert dialog.profile.id == profile.id and dialog.profile.model_path == profile.model_path
    window.settings_fields['language'].setCurrentIndex(0)
    assert '已就绪' in window.state_label.text()
    assert window.download_table.item(0, 1).text() == '已暂停'
    assert window.repo_table.item(0, 3).text() == '模型'
    assert window.downloads.records[0]['state'] == 'Paused'
    assert Store(tmp_path).settings['language'] == 'zh'
    window.copy_model(); assert app.clipboard().text() == 'actual-api-id'
    window.tray.quitting = True; window.tray.icon.hide(); window.shutdown(); window.deleteLater(); app.processEvents()

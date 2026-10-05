import json
from dataclasses import asdict

import pytest

from lmm.config import Profile, Store


def test_portable_settings_and_profile_roundtrip(tmp_path):
    store = Store(tmp_path)
    profile = Profile("qwen", "Qwen", model_path="models/qwen.gguf", extra_args=["--ctx-size", "4096"])
    store.put_profile(profile)
    store.settings["models_dir"] = "other-models"
    store.save()
    restored = Store(tmp_path)
    assert asdict(restored.profiles[0]) == asdict(profile)
    assert restored.models == tmp_path / "other-models"


def test_invalid_profile_and_corrupt_settings_are_not_ignored(tmp_path):
    with pytest.raises(ValueError):
        Profile("../outside", "Bad").validate()
    with pytest.raises(ValueError):
        Profile("bad", "Bad", extra_args=["--port=8001"]).validate()
    store = Store(tmp_path)
    path = store.config / "settings.json"
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        Store(tmp_path)
    assert path.read_text() == "broken"


def test_gui_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from lmm.gui import Window
    app = QApplication.instance() or QApplication([])
    window = Window(Store(tmp_path))
    window.show(); app.processEvents()
    assert window.nav.count() == 7
    window.settings_fields["default_port"].setValue(8100)
    window.save_settings()
    assert Store(tmp_path).settings["default_port"] == 8100
    window.hide(); window.deleteLater(); app.processEvents()

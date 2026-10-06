import threading
import pytest
from lmm.config import Store,Profile
from lmm.processes import Manager
from lmm.adapters import get_adapter

def test_switch_rolls_back_failed_target_without_stopping_other_ports(tmp_path,monkeypatch):
    store=Store(tmp_path)
    model=store.models/'model.gguf';model.touch()
    for identity,port in [('old',18000),('new',18000),('other',18010)]:
        store.put_profile(Profile(identity,identity,model_path=str(model),port=port))
    binary=get_adapter('llama_cpp').executable(store);binary.parent.mkdir(parents=True);binary.touch()
    manager=Manager(store);running={'old','other'};calls=[]
    monkeypatch.setattr(manager,'is_running',lambda identity:identity in running)
    monkeypatch.setattr(manager,'stop',lambda identity:(calls.append(('stop',identity)),running.discard(identity)))
    def start(identity):calls.append(('start',identity));running.add(identity);return {'pid':1}
    monkeypatch.setattr(manager,'start',start)
    monkeypatch.setattr(manager,'wait_ready_many',lambda ids:None)
    def failed(*args,**kwargs):raise RuntimeError('Target health failed')
    monkeypatch.setattr('lmm.api.wait_ready',failed)
    with pytest.raises(RuntimeError,match='health'):manager.switch('new')
    assert running=={'old','other'} and ('stop','other') not in calls
    monkeypatch.setattr('lmm.api.wait_ready',lambda *a,**k:{'state':'READY'})
    assert manager.switch('new')['state']=='READY'
    assert running=={'new','other'}

def test_catalog_visible_reserved_actions_disabled_and_completed_model_configured(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from lmm.gui import Window
    app=QApplication.instance() or QApplication([])
    store=Store(tmp_path);store.put_profile(Profile('qwen3-asr-17b-q8','Qwen',compatibility_proxy=True))
    window=Window(store)
    try:
        index=window.profile_combo.findData('catalog:fun-asr-nano-2512')
        assert index>=0
        window.profile_combo.setCurrentIndex(index)
        assert window.service_buttons['start'].isEnabled()
        assert window.service_buttons['start'].text()=='安装并切换'
        calls=[]
        monkeypatch.setattr(window.jobs,'submit',lambda *a,**k:calls.append(a))
        for rid in ('nvidia_nim','faster_whisper','vllm','ollama','lm_studio'):
            window.runtime_selector.setCurrentIndex(window.runtime_selector.findData(rid))
            assert not any(b.isEnabled() for b in window.runtime_buttons)
            window.check_runtime();window.install_runtime();window.install_staged_runtime()
        assert not calls
        window.runtime_selector.setCurrentIndex(window.runtime_selector.findData('audio_cpp'))
        assert all(b.isEnabled() for b in window.runtime_buttons[:2])
        manifest=window.registry.entries['fun-asr-nano-2512']
        receipt={'filename':'fun-q8_0.gguf','path':'models/fun-q8_0.gguf','is_mmproj':False}
        window.offer_imported_profile([receipt],{'manifest':manifest,'metadata':{},'roles':{'model':receipt['filename']}})
        profile=store.get_profile(manifest['id'])
        assert window.profile_combo.currentData()==profile.id
        assert profile.runtime_id=='audio_cpp' and profile.compatibility_proxy and profile.proxy_port==8001
        assert profile.runtime_options['family']=='fun_asr_nano' and window.nav.currentRow()==0
        assert window.profile_combo.findData('catalog:'+profile.id)==-1
    finally:window.hide();window.shutdown();window.deleteLater();app.processEvents()

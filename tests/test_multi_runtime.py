import io
import json
import struct
import threading
import wave
from types import SimpleNamespace
import httpx
import pytest
from lmm.adapters import adapters,get_adapter
from lmm.config import Store,Profile,atomic_json
from lmm.registry import ModelRegistry,inspect_local
from lmm.processes import build_command
from lmm.runtime import Runtime
from lmm.jobs import Control
from lmm.transcribe_service import make_server

def test_audio_readiness_accepts_only_known_missing_file_error():
    adapter=get_adapter('audio_cpp')
    assert adapter.transcription_route_available(httpx.Response(500,json={'error':{'message':"multipart transcription request requires a non-empty 'file' field"}}))
    assert not adapter.transcription_route_available(httpx.Response(500,json={'error':{'message':'CUDA allocation failed'}}))
    assert not get_adapter('llama_cpp').transcription_route_available(httpx.Response(500))

def test_transcribe_release_includes_cuda_dependencies(monkeypatch):
    import lmm.net as net
    def request(url,control):
        if 'api.github.com' in url:
            return {'tag_name':'v1','html_url':'https://github.com/example/runtime/releases/tag/v1','assets':[{'name':'transcribe_cpp-1-py3-none-any.whl'},{'name':'transcribe_cpp_native_cu12-1-py3-none-win_amd64.whl'}]}
        name=url.split('/')[-2]
        return {'urls':[{'filename':name+'-1-py3-none-win_amd64.whl','url':'https://files.pythonhosted.org/'+name,'size':100,'digests':{'sha256':'a'*64}}]}
    monkeypatch.setattr(net,'request_json',request)
    release=get_adapter('transcribe_cpp').resolve_release(Control(),{'cuda_major':13})
    assert len(release['assets'])==4
    assert all(a['digest']=='sha256:'+'a'*64 for a in release['assets'][2:])

def test_source_resolution_uses_metadata_without_download(tmp_path,monkeypatch):
    import lmm.sources as sources
    calls=[]
    class Models:
        def repository(self,repo,control,revision='main'):
            calls.append((repo,revision));return {'repo_id':repo,'files':[]}
    resolver=sources.Sources(Models())
    result=resolver.resolve('https://huggingface.co/vendor/model/blob/revision/model.gguf',Control())
    assert result['suggested_files']==['model.gguf'] and calls==[('vendor/model','revision')]
    def reply(request):
        calls.append(request.method)
        return httpx.Response(405) if request.method=='HEAD' else httpx.Response(206,headers={'Content-Range':'bytes 0-0/1024','ETag':'fixed'},content=b'x')
    monkeypatch.setattr(sources,'client',lambda **kw:httpx.Client(transport=httpx.MockTransport(reply)))
    result=resolver.resolve('https://example.test/model.bin',Control())
    assert result['files'][0]['size']==1024 and calls[-2:]==['HEAD','GET']
    with pytest.raises(ValueError,match='credentials'):resolver.resolve('https://user:secret@example.test/model',Control())

def test_unicode_model_link_does_not_copy_or_change_source(tmp_path):
    import os
    from lmm.runtime_paths import ascii_model_path
    if os.name!='nt':pytest.skip('Windows engine workaround')
    source=tmp_path/'模型.gguf';source.write_bytes(b'weights')
    result=ascii_model_path(source)
    assert str(result).isascii() and os.path.samefile(source,result) and source.read_bytes()==b'weights'

def test_legacy_profiles_migrate_without_guessing_new_gguf(tmp_path):
    store=Store(tmp_path)
    atomic_json(store.config/'profiles.json',[{'id':'old','name':'Old','model_path':'old.gguf'}])
    assert Store(tmp_path).profiles[0].runtime_id=='llama_cpp'
    unknown=store.models/'unfamiliar.gguf';unknown.write_bytes(b'GGUF')
    registry=ModelRegistry(store)
    assert not any(row['recommended'] for row in registry.compatibility(inspect_local(unknown)))
    with pytest.raises(ValueError,match='Select a registered'):
        build_command(Profile('new','New',runtime_id='',model_path=str(unknown)),store,'--model')

def test_manifest_adds_model_without_core_changes(tmp_path):
    store=Store(tmp_path);registry=ModelRegistry(store)
    manifest=tmp_path/'new.yaml'
    manifest.write_text('''id: example-asr
task: asr
source: {type: huggingface, repo: vendor/new-gguf}
runtime: {recommended: audio_cpp, options: {family: new_asr}}
files: {model: {pattern: "*q8.gguf"}}
''')
    result=registry.import_file(manifest)
    metadata={'repo_id':'vendor/new-gguf','files':[{'filename':'new-q8.gguf'}]}
    assert registry.select_files(result,metadata)=={'model':'new-q8.gguf'}
    assert next(row for row in registry.compatibility(metadata) if row['recommended'])['id']=='audio_cpp'
    assert 'example-asr' in ModelRegistry(store).entries
    model=store.models/'new-q8.gguf';model.touch()
    profile=Profile('new','New',runtime_id='audio_cpp',model_path=str(model),requires_mmproj=False,runtime_options={'family':'new_asr'})
    command=build_command(profile,store,'--config FILE --no-ui')
    config=json.loads((store.config/'launch/new.json').read_text())
    assert 'audiocpp_server.exe' in command[0] and config['models'][0]['family']=='new_asr'
    assert config['lazy_load'] is False and config['log_request_body'] is False
    manifest.write_text('!!python/object/apply:os.system ["unexpected"]')
    with pytest.raises(Exception):registry.import_file(manifest)

def test_evidence_conflicts_and_runtime_isolation(tmp_path):
    store=Store(tmp_path);registry=ModelRegistry(store)
    rows=registry.compatibility({'card':'Supports audio.cpp and transcribe.cpp','files':[]})
    assert not any(row['recommended'] for row in rows)
    assert len(adapters())>=8
    assert get_adapter('ollama').implemented is False
    a=Runtime(store,get_adapter('audio_cpp'));t=Runtime(store,get_adapter('transcribe_cpp'))
    assert a.directory!=t.directory!=store.runtime
    assert a.receipt('transaction')!=t.receipt('transaction')
    with pytest.raises(ValueError,match='reserved'):get_adapter('ollama').require_implemented()

def test_bounded_gguf_architecture_reader(tmp_path):
    def text(s):b=s.encode();return struct.pack('<Q',len(b))+b
    file=tmp_path/'new-Q8_0.gguf'
    file.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,1)+text('general.architecture')+struct.pack('<I',8)+text('different-engine'))
    result=inspect_local(file)
    assert result['architecture']=='different-engine' and result['quantization']=='Q8_0'
    file.write_bytes(b'GGUF'+struct.pack('<IQQQ',3,0,1,2**50))
    assert inspect_local(file)['architecture']==''

def test_transcribe_bridge_health_validation_and_real_pcm(tmp_path):
    captured=[]
    class Session:
        def run(self,pcm,**kw):captured.append((pcm,kw));return SimpleNamespace(text='本地识别')
    profile=Profile('asr','ASR',runtime_id='transcribe_cpp')
    server=make_server(profile,Session(),('127.0.0.1',0))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        with httpx.Client(trust_env=False) as c:
            assert c.get(url+'/health').status_code==200
            assert c.get(url+'/v1/models').json()['data'][0]['id']=='asr'
            assert c.post(url+'/v1/audio/transcriptions',files={'model':(None,'asr')}).status_code==400
            output=io.BytesIO()
            with wave.open(output,'wb') as wav:wav.setparams((1,2,16000,0,'NONE',''));wav.writeframes(b'\x01\x00'*160)
            r=c.post(url+'/v1/audio/transcriptions',data={'model':'asr'},files={'file':('clip.wav',output.getvalue(),'audio/wav')})
            assert r.json()['text']=='本地识别' and len(captured[0][0])==160
            assert c.post(url+'/v1/chat/completions',json={}).status_code==404
    finally:server.shutdown();server.server_close();thread.join()

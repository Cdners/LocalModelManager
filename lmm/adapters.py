"""Inference-engine contracts. Models are data from ModelRegistry, not branches here."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import re
from .config import atomic_json

@dataclass
class RuntimeAdapter:
    id: str
    name: str
    supported_tasks: tuple[str, ...]
    repository: str = ''
    executable_name: str = ''
    implemented: bool = False

    def runtime_dir(self, store):
        if self.id == 'llama_cpp': return store.runtime
        return store.path(store.settings.get('runtime_paths', {}).get(self.id, 'runtime/' + self.id))

    def executable(self, store):
        return self.runtime_dir(store) / self.executable_name

    def detect_compatibility(self, metadata, registry):
        return next(row for row in registry.compatibility(metadata) if row['id'] == self.id)

    def check_update(self, store, control, progress=lambda _: None):
        from .runtime import Runtime
        self.require_implemented()
        return Runtime(store, self).check(control, progress)

    def install_runtime(self, store, release, control, manager, progress=lambda _: None):
        from .runtime import Runtime
        self.require_implemented()
        runtime = Runtime(store, self)
        stage = runtime.stage(release, control, progress)
        return runtime.install(stage, control, lambda: manager.stop_runtime(self.id), manager.start_many, manager.wait_ready_many)

    def require_implemented(self):
        if not self.implemented: raise ValueError(self.name + ': adapter reserved, implementation not installed.')

    def resolve_release(self, control, hardware):
        raise NotImplementedError(self.name + ': release provider is not implemented.')

    def verify_stage(self, stage, release):
        import shutil
        from .runtime import run_binary
        servers = list(stage.rglob(self.executable_name))
        if len(servers) != 1: raise ValueError('Runtime package must contain one ' + self.executable_name)
        if servers[0].parent != stage:
            for file in servers[0].parent.iterdir():
                if file.is_file(): shutil.copy2(file, stage / file.name)
        for dll in list(stage.rglob('*.dll')):
            if dll.parent != stage and not (stage / dll.name).exists(): shutil.copy2(dll, stage / dll.name)
        return run_binary(stage / self.executable_name, '--version'), run_binary(stage / self.executable_name, '--list-devices', timeout=45)

    def build_launch_command(self, profile, store, help_text=''):
        raise NotImplementedError(self.name + ': adapter is not implemented.')

    def start(self, manager, profile_id): return manager.start(profile_id)
    def stop(self, manager, profile_id): return manager.stop(profile_id)

    def health_check(self, profile):
        from .api import snapshot
        return snapshot(profile)

    def transcription_route_available(self, response):
        return response.status_code in {200, 400, 415, 422}

    def get_model_id(self, profile):
        values = self.health_check(profile)['model_ids']
        if not values: raise ValueError('Model ID is not available yet.')
        return values[0]

    def expose_capabilities(self):
        routes = {'asr':'/v1/audio/transcriptions', 'llm':'/v1/chat/completions',
                  'vision':'/v1/chat/completions', 'embedding':'/v1/embeddings',
                  'reranker':'/v1/rerank', 'tts':'/v1/audio/speech'}
        return {'tasks': self.supported_tasks, 'routes': [routes[t] for t in self.supported_tasks], 'implemented': self.implemented}

    def probe(self, store):
        from .runtime import run_binary
        self.require_implemented()
        return run_binary(self.executable(store), '--help')

class LlamaAdapter(RuntimeAdapter):
    def __init__(self): super().__init__('llama_cpp', 'llama.cpp', ('asr','llm','embedding','vision','reranker'), 'ggml-org/llama.cpp', 'llama-server.exe', True)
    def build_launch_command(self, profile, store, help_text=''):
        from .processes import build_llama_command
        return build_llama_command(profile, store, help_text)
    def resolve_release(self, control, hardware):
        from .runtime import latest_release
        return latest_release(control, hardware['cuda_major'])

class AudioAdapter(RuntimeAdapter):
    def __init__(self): super().__init__('audio_cpp', 'audio.cpp', ('asr','tts'), '0xShug0/audio.cpp', 'audiocpp_server.exe', True)
    def resolve_release(self, control, hardware):
        release = github_release(self.repository, control)
        candidates = [a for a in release['assets'] if re.search(r'windows-x64-cuda(\d+)\.(\d+)', a['name']) and a['name'].endswith('.zip') and '-bin-' in a['name'] and int(re.search(r'cuda(\d+)', a['name'])[1]) <= hardware['cuda_major']]
        if not candidates: raise ValueError('No compatible Windows CUDA runtime asset.')
        selected = max(candidates, key=lambda a: tuple(int(v) for v in re.search(r'cuda(\d+)\.(\d+)', a['name']).groups()))
        cuda = re.search(r'cuda[\d.]+', selected['name'])[0].rstrip('.')
        assets = [selected] + [a for a in release['assets'] if 'cudart-windows-x64-' + cuda + '.zip' in a['name']]
        return release_record(release, assets)
    def transcription_route_available(self, response):
        if super().transcription_route_available(response): return True
        # audio.cpp 0.9.0 reports this specific input validation failure as 500.
        # Other server errors must continue to fail the readiness check.
        try: message = response.json().get('error', {}).get('message')
        except (ValueError, AttributeError): return False
        return response.status_code == 500 and message == "multipart transcription request requires a non-empty 'file' field"
    def build_launch_command(self, profile, store, help_text=''):
        profile.validate()
        path = store.path(profile.model_path)
        if not path.exists(): raise ValueError('Model file or directory is missing.')
        family = profile.runtime_options.get('family') or profile.architecture
        if not family or not re.fullmatch(r'[a-zA-Z0-9_-]+', family):
            raise ValueError('audio.cpp requires a family from the manifest or explicit user selection.')
        if '--config' not in help_text: raise ValueError('audio.cpp server does not advertise --config.')
        allowed = {'load_options', 'session_options', 'default_request_options'}
        model = {k: v for k, v in profile.runtime_options.items() if k in allowed}
        from .runtime_paths import ascii_model_path
        model_path = str(ascii_model_path(path))
        model.update(id=profile.id, family=family, path=model_path, task=profile.type, mode='offline')
        config = store.config / 'launch' / (profile.id + '.json')
        atomic_json(config, {'host': profile.host, 'port': profile.port, 'backend': profile.backend,
            'lazy_load': False, 'log_request_body': False, 'max_request_body_bytes': 64*1024**2, 'models': [model]})
        # Engine configuration comes from typed fields. Extra argv cannot replace
        # the config, host, security settings or model after validation.
        if profile.extra_args: raise ValueError('Use audio.cpp runtime options, not extra command arguments.')
        return [str(self.executable(store)), '--config', str(config), '--no-ui']

class TranscribeAdapter(RuntimeAdapter):
    def __init__(self): super().__init__('transcribe_cpp', 'transcribe.cpp', ('asr',), 'handy-computer/transcribe.cpp', 'transcribe_cpp/__init__.py', True)
    def resolve_release(self, control, hardware):
        from .net import request_json
        if hardware['cuda_major'] < 12: raise ValueError('transcribe.cpp requires a CUDA 12 compatible driver.')
        release = github_release(self.repository, control)
        assets = [a for a in release['assets'] if (a['name'].startswith('transcribe_cpp-') and a['name'].endswith('-py3-none-any.whl')) or (a['name'].startswith('transcribe_cpp_native_cu12-') and a['name'].endswith('-win_amd64.whl'))]
        if len(assets) != 2: raise ValueError('Matching Python binding and Windows CUDA native wheel are required.')
        # Resolve official dependency wheels as files, without pip/global installs.
        for package in ('nvidia-cuda-runtime-cu12', 'nvidia-cublas-cu12'):
            dependency = request_json('https://pypi.org/pypi/' + package + '/json', control)
            wheels = [f for f in dependency['urls'] if f['filename'].endswith('-py3-none-win_amd64.whl') and not f.get('yanked')]
            if len(wheels) != 1: raise ValueError('A unique Windows CUDA dependency wheel is required: ' + package)
            item = wheels[0]
            assets.append({'name':item['filename'], 'browser_download_url':item['url'], 'size':item['size'], 'digest':'sha256:'+item['digests']['sha256']})
        return release_record(release, assets)

    def verify_stage(self, stage, release):
        import subprocess
        from .processes import helper_command
        from .runtime import NO_WINDOW
        from .config import read_json
        if not (stage / self.executable_name).exists(): raise ValueError('Runtime wheel is incomplete.')
        result = stage / 'probe-result.json'
        result.unlink(missing_ok=True)
        try:
            output = subprocess.run(helper_command('--runtime-probe', self.id, '--runtime-root', str(stage), '--probe-output', str(result)), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60, creationflags=NO_WINDOW)
            if output.returncode or not result.exists(): raise ValueError('transcribe.cpp ABI/device probe failed: ' + output.stderr[-1000:])
            return release['binary_tag'], read_json(result,{})['devices']
        finally: result.unlink(missing_ok=True)
    def build_launch_command(self, profile, store, help_text=''):
        from .processes import helper_command
        if not store.path(profile.model_path).is_file(): raise ValueError('A complete transcribe.cpp model file is required.')
        if profile.extra_args: raise ValueError('transcribe.cpp uses runtime options, not command arguments.')
        return helper_command('--adapter-service', profile.id, '--root', str(store.root))
    def probe(self, store):
        from .transcribe_service import load_binding
        module = load_binding(self.runtime_dir(store))
        return str(module.backends())

def github_release(repository, control):
    from .net import request_json
    release = request_json('https://api.github.com/repos/' + repository + '/releases/latest', control)
    if release.get('draft') or release.get('prerelease'): raise ValueError('Expected a stable runtime release.')
    return release

def release_record(release, assets):
    return {'stable_tag':release['tag_name'], 'binary_tag':release['tag_name'], 'assets':assets, 'source_url':release['html_url'], 'published_at':release.get('published_at')}

_ADAPTERS = {}
_initialized = False
def register_adapter(adapter):
    if not _initialized: adapters()
    if adapter.id in _ADAPTERS: raise ValueError('Duplicate runtime adapter ID: ' + adapter.id)
    _ADAPTERS[adapter.id] = adapter

def adapters():
    global _initialized
    if not _initialized:
        _initialized = True
        for adapter in (LlamaAdapter(), AudioAdapter(), TranscribeAdapter(),
            RuntimeAdapter('faster_whisper','faster-whisper',('asr',)),
            RuntimeAdapter('ollama','Ollama',('llm','vision','embedding')),
            RuntimeAdapter('lm_studio','LM Studio',('llm','vision','embedding')),
            RuntimeAdapter('vllm','vLLM',('llm','vision','embedding','reranker','asr','tts')),
            RuntimeAdapter('nvidia_nim','NVIDIA NIM',('asr','llm','vision','embedding','reranker','tts'))):
            register_adapter(adapter)
    return _ADAPTERS

def get_adapter(identity):
    if identity not in adapters(): raise ValueError('Select a registered runtime adapter; the model format alone is insufficient.')
    return adapters()[identity]

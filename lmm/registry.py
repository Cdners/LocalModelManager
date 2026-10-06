"""Data-only model catalog. A filename extension never selects an inference engine."""
from __future__ import annotations
import fnmatch
import json
from pathlib import Path
import re
import struct
import yaml
from .config import atomic_json, read_json

TASKS = {'asr', 'llm', 'embedding', 'vision', 'reranker', 'tts'}

def validate_manifest(data):
    if not isinstance(data, dict): raise ValueError('Manifest must be an object.')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}', str(data.get('id', ''))):
        raise ValueError('Manifest needs a safe, unique ID.')
    if data.get('task') not in TASKS: raise ValueError('Unsupported manifest task.')
    runtime = data.get('runtime', {})
    if not isinstance(runtime, dict): raise ValueError('Runtime must be an object.')
    recommended = runtime.get('recommended') or runtime.get('adapter')
    if not isinstance(recommended, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', recommended):
        raise ValueError('Manifest needs a recommended runtime adapter.')
    source = data.get('source', {})
    if not isinstance(source, dict): raise ValueError('Source must be an object.')
    if source.get('type') not in {'huggingface', 'github', 'https', 'local'}:
        raise ValueError('Unsupported model source.')
    required = 'repo' if source['type'] == 'huggingface' else 'path' if source['type'] == 'local' else 'url'
    if not isinstance(source.get(required) or (source.get('repo') if source['type']=='github' else None), str):
        raise ValueError('Manifest source is missing its repository, URL or path.')
    files = data.get('files', {})
    if not isinstance(files, dict) or 'model' not in files: raise ValueError('Manifest needs a model file role.')
    for role, spec in files.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', role) or not isinstance(spec, dict): raise ValueError('Invalid file role.')
        pattern = spec.get('pattern', '')
        if not isinstance(pattern, str) or not pattern or '..' in pattern or pattern.startswith(('/', '\\')) or ':' in pattern:
            raise ValueError('Unsafe manifest file pattern.')
    if not isinstance(runtime.get('options', {}), dict): raise ValueError('Runtime options must be an object.')
    # Imported YAML describes data, never executable hooks or Python modules.
    if any(k in data for k in ('command', 'exec', 'script', 'hooks', 'python')):
        raise ValueError('Executable manifest hooks are not supported.')
    return data | {'name': data.get('name', data['id']), 'runtime': runtime | {'recommended': recommended}}

class ModelRegistry:
    def __init__(self, store):
        self.store = store
        builtin = Path(__file__).resolve().parent.parent / 'assets' / 'model_registry.json'
        self.entries = {m['id']: validate_manifest(m) for m in read_json(builtin, [])}
        for path in sorted((store.config / 'manifests').glob('*.json')):
            manifest = validate_manifest(read_json(path, {})); self.entries[manifest['id']] = manifest

    def import_file(self, path):
        path = Path(path)
        if path.stat().st_size > 1024 * 1024: raise ValueError('Manifest exceeds 1 MiB.')
        manifest = validate_manifest(yaml.safe_load(path.read_text(encoding='utf-8-sig')))
        atomic_json(self.store.config / 'manifests' / (manifest['id'] + '.json'), manifest)
        self.entries[manifest['id']] = manifest
        return manifest

    def match(self, metadata):
        repo = metadata.get('repo_id', '')
        return [m for m in self.entries.values() if repo and m['source'].get('repo', '').lower() == repo.lower()]

    def compatibility(self, metadata):
        from .adapters import adapters
        evidence = {}
        matches = self.match(metadata)
        for m in matches:
            for rid in m['runtime'].get('compatible', [m['runtime']['recommended']]):
                evidence[rid] = (100, 'Model Registry: ' + m['id'])
        if not evidence:
            text = str(metadata.get('card', '')) + ' ' + str(metadata.get('tags', ''))
            for rid, adapter in adapters().items():
                if adapter.name.lower() in text.lower(): evidence[rid] = (70, 'Repository metadata / README')
            for m in self.entries.values():
                required = m.get('companions', [])
                names = [f['filename'].lower() for f in metadata.get('files', [])]
                if required and all(any(fnmatch.fnmatch(n, p.lower()) for n in names) for p in required):
                    evidence.setdefault(m['runtime']['recommended'], (60, 'Companion files'))
                if metadata.get('architecture') and metadata['architecture'] in m.get('architectures', []):
                    evidence.setdefault(m['runtime']['recommended'], (50, 'Known architecture'))
        for rid, passed in metadata.get('runtime_probe', {}).items():
            if passed is True:evidence.setdefault(rid, (40, 'Successful runtime probe'))
        incompatible = {rid for m in matches for rid in m['runtime'].get('incompatible', [])}
        incompatible.update(rid for rid, passed in metadata.get('runtime_probe', {}).items() if passed is False)
        viable = {rid: value for rid, value in evidence.items() if rid not in incompatible}
        best = max((score for score, _ in viable.values()), default=0)
        winners = [rid for rid, (score, _) in viable.items() if score == best]
        recommended = winners[0] if len(winners) == 1 else None
        return [{'id': rid, 'name': a.name, 'status': 'incompatible' if rid in incompatible else 'compatible' if rid in evidence else 'unknown',
                 'recommended': rid == recommended and rid not in incompatible, 'reason': evidence.get(rid, (0, 'User selection / runtime probe required'))[1],
                 'implemented': a.implemented} for rid, a in adapters().items()]

    def select_files(self, manifest, metadata):
        selected = {}
        for role, spec in manifest['files'].items():
            names = [f['filename'] for f in metadata['files'] if fnmatch.fnmatch(f['filename'].lower(), spec['pattern'].lower())]
            if len(names) != 1:
                if spec.get('optional') and not names: continue
                raise ValueError(f'{role}: expected exactly one matching file; select an unambiguous manifest pattern.')
            selected[role] = names[0]
        return selected

def inspect_local(path):
    path = Path(path).resolve()
    if not path.exists(): raise ValueError('Local model does not exist.')
    files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
    metadata = {'source': 'local', 'path': str(path), 'size': sum(p.stat().st_size for p in files),
                'format': 'directory' if path.is_dir() else path.suffix.lstrip('.').lower(),
                'architecture': '', 'quantization': '', 'files': [{'filename': p.relative_to(path).as_posix() if path.is_dir() else p.name, 'size': p.stat().st_size} for p in files]}
    if path.is_file() and path.suffix.lower() == '.gguf':
        metadata.update(gguf_metadata(path))
    else:
        config = path / 'config.json'
        if path.is_dir() and config.exists() and config.stat().st_size < 1024 * 1024:
            data = read_json(config, {}); metadata['architecture'] = data.get('model_type', '')
    quant = re.search(r'(Q\d(?:_[A-Z0-9]+)*|BF16|F16|F32)', path.name, re.I)
    if quant: metadata['quantization'] = quant[1].upper()
    if path.is_file():
        companions = [p for p in path.parent.iterdir() if p.is_file() and (p.name.lower().startswith('mmproj') or p.name in {'config.json','tokenizer.json','tokens.txt'})]
        metadata['companions'] = [p.name for p in companions]
        metadata['files'] += [{'filename':p.name,'size':p.stat().st_size} for p in companions if p != path]
        receipt = path.with_name(path.name+'.metadata.json')
        if receipt.exists() and receipt.stat().st_size < 1024*1024:
            metadata['repo_id'] = read_json(receipt,{}).get('repo_id','')
    return metadata

def gguf_metadata(path):
    """Read a bounded metadata prefix; malformed/huge metadata stays unknown."""
    result = {}
    with Path(path).open('rb') as stream:
        def read(n):
            if n > 16 * 1024**2 or stream.tell() + n > 16 * 1024**2: raise ValueError('GGUF metadata limit')
            data = stream.read(n)
            if len(data) != n: raise ValueError('Truncated GGUF')
            return data
        def number(fmt): return struct.unpack('<' + fmt, read(struct.calcsize(fmt)))[0]
        def string(): return read(number('Q')).decode('utf-8')
        def value(kind, depth=0):
            if depth > 2: raise ValueError('Nested GGUF array')
            formats = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in formats: return number(formats[kind])
            if kind == 8: return string()
            if kind == 9:
                subtype, count = number('I'), number('Q')
                if count > 1000000: raise ValueError('GGUF array limit')
                for _ in range(count): value(subtype, depth+1)
                return None
            raise ValueError('Unknown GGUF metadata type')
        try:
            if read(4) != b'GGUF' or number('I') not in (2,3): return result
            number('Q'); count = number('Q')
            for _ in range(min(count, 10000)):
                key = string(); item = value(number('I'))
                if key == 'general.architecture': result['architecture'] = item
                elif key == 'general.file_type': result['gguf_file_type'] = item
        except (ValueError, UnicodeError, struct.error): pass
    return result

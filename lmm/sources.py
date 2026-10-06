"""Providers resolve metadata/URLs; only DownloadManager transfers model data."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote
from .net import client, request_json
from .registry import inspect_local

def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an HTTP(S) source without embedded credentials.')
    return parsed

class Sources:
    def __init__(self, models): self.models = models
    def resolve(self, value, control):
        value = value.strip()
        if not value: raise ValueError('Enter a model source.')
        if '://' not in value and Path(value).exists(): return inspect_local(value)
        if '://' not in value: return self.models.repository(value, control)
        url = validate_url(value)
        parts = [unquote(x) for x in url.path.split('/') if x]
        if url.hostname in {'huggingface.co','www.huggingface.co'}:
            if len(parts) < 2: raise ValueError('Enter a Hugging Face model repository URL.')
            revision = parts[3] if len(parts)>3 and parts[2] in {'tree','blob','resolve'} else 'main'
            result = self.models.repository('/'.join(parts[:2]), control, revision)
            if len(parts)>4 and parts[2] in {'blob','resolve'}:
                selected = '/'.join(parts[4:]); result['suggested_files'] = [selected]
            return result
        if url.hostname == 'github.com' and len(parts)>=3 and parts[2]=='releases' and (len(parts)<4 or parts[3] != 'download'):
            repo = '/'.join(parts[:2])
            endpoint = '/tags/' + '/'.join(parts[4:]) if len(parts)>4 and parts[3]=='tag' else '/latest'
            release = request_json('https://api.github.com/repos/'+repo+'/releases'+endpoint,control)
            if release.get('draft'): raise ValueError('Draft releases cannot be imported.')
            files = []
            for item in release['assets']:
                name = item['name']
                if Path(name).name != name or any(c in name for c in '\\/:'): raise ValueError('Unsafe release filename.')
                files.append({'filename':name,'url':item['browser_download_url'],'size':item['size'],
                    'sha256':(item.get('digest') or '').removeprefix('sha256:') or None,'is_mmproj':name.lower().startswith('mmproj')})
            return {'source_type':'github','repo_id':repo,'revision':hashlib.sha256(str(release['id']).encode()).hexdigest(),
                    'files':files,'card':release.get('body',''),'source_url':value}
        with client(network=control.network) as session:
            response = session.head(value)
            if response.status_code in {405,501}:
                with session.stream('GET',value,headers={'Range':'bytes=0-0','Accept-Encoding':'identity'}) as probe:
                    probe.raise_for_status(); headers = dict(probe.headers)
            else:
                response.raise_for_status(); headers = dict(response.headers)
        size = headers.get('content-range','').split('/')[-1] if headers.get('content-range') else headers.get('content-length')
        if not size or not size.isdigit(): raise ValueError('Source must expose a file size before downloading.')
        filename = parts[-1] if parts else 'model.bin'
        if Path(filename).name != filename or any(c in filename for c in '\\/:'): raise ValueError('Unsafe URL filename.')
        identity = hashlib.sha256((value+'|'+headers.get('etag','')+'|'+size).encode()).hexdigest()
        return {'source_type':'https','repo_id':'http-'+hashlib.sha256(value.encode()).hexdigest()[:16],
            'revision':identity,'files':[{'filename':filename,'size':int(size),'url':value,'etag':headers.get('etag'),
            'sha256':None,'is_mmproj':False}],'source_url':value}

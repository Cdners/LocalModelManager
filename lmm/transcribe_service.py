"""OpenAI ASR bridge for the upstream ctypes-only transcribe.cpp binding."""
from __future__ import annotations
from array import array
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import threading
import wave

_dll_handles = []
_cuda_libraries = []
def load_binding(directory):
    directory = Path(directory).resolve()
    libraries = list(directory.rglob('transcribe.dll'))
    if len(libraries) != 1: raise ValueError('Runtime must contain exactly one transcribe.dll.')
    if os.name == 'nt':
        for path in sorted({p.parent for p in directory.rglob('*.dll')}):
            _dll_handles.append(os.add_dll_directory(str(path)))
        import ctypes
        for name in ('cudart64_12.dll', 'cublasLt64_12.dll', 'cublas64_12.dll'):
            matches = list(directory.rglob(name))
            if len(matches) != 1: raise ValueError('Missing or ambiguous CUDA dependency: ' + name)
            _cuda_libraries.append(ctypes.CDLL(str(matches[0])))
    os.environ['TRANSCRIBE_LIBRARY'] = str(libraries[0])
    os.environ['TRANSCRIBE_NATIVE_PROVIDER'] = 'cu12'
    sys.path.insert(0, str(directory))
    import transcribe_cpp
    return transcribe_cpp

def decode_wav(data):
    import audioop
    with wave.open(io.BytesIO(data), 'rb') as audio:
        channels, width, rate = audio.getnchannels(), audio.getsampwidth(), audio.getframerate()
        if channels not in (1,2) or width not in (1,2,3,4) or audio.getcomptype() != 'NONE':
            raise ValueError('Use an uncompressed mono/stereo PCM WAV file.')
        pcm = audio.readframes(audio.getnframes())
    if width == 1: pcm = audioop.bias(pcm, 1, -128)
    if channels == 2: pcm = audioop.tomono(pcm, width, 0.5, 0.5)
    pcm = audioop.lin2lin(pcm, width, 2)
    if rate != 16000: pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    samples = array('h', pcm)
    if sys.byteorder != 'little': samples.byteswap()
    return array('f', (v / 32768 for v in samples))

def make_server(profile, session, address=None):
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, status, value):
            data = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            if self.path == '/health': self.reply(200, {'status':'ok', 'runtime':'transcribe_cpp'})
            elif self.path == '/v1/models': self.reply(200, {'object':'list', 'data':[{'id':profile.id,'object':'model','owned_by':'local'}]})
            else: self.reply(404, {'error':'Unsupported endpoint'})
        def do_POST(self):
            if self.path != '/v1/audio/transcriptions': self.reply(404, {'error':'Unsupported capability'}); return
            self.connection.settimeout(30)
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 64*1024**2 or self.headers.get('Transfer-Encoding'):
                    self.reply(413, {'error':'Audio request must have a bounded Content-Length'}); return
                content_type = self.headers.get('Content-Type','')
                if not content_type.startswith('multipart/form-data'): self.reply(415, {'error':'Use multipart/form-data'}); return
                body = self.rfile.read(length)
                if len(body) != length: raise ValueError('Incomplete body')
                message = BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
                parts = {p.get_param('name',header='content-disposition'):p.get_payload(decode=True) for p in message.iter_parts()}
                if not parts.get('file'): self.reply(400, {'error':'Missing file'}); return
                if parts.get('model', profile.id.encode()).decode() != profile.id:
                    self.reply(404, {'error':'Unknown model'}); return
                if parts.get('response_format',b'json') not in (b'json', b'verbose_json'):
                    self.reply(400, {'error':'Supported response formats: json, verbose_json'}); return
                if not lock.acquire(blocking=False): self.reply(429, {'error':'Model is busy'}); return
                try:
                    samples = decode_wav(parts['file'])
                    options = {}
                    language = parts.get('language', b'').decode().strip()
                    if language: options['language'] = language
                    result = session.run(samples, **options)
                    self.reply(200, {'text': result.text})
                finally: lock.release()
            except (ValueError, wave.Error, UnicodeError): self.reply(400, {'error':'Invalid PCM WAV or request fields'})
            except Exception: self.reply(500, {'error':'Runtime inference failed; check runtime compatibility and GPU memory'})
    server = ThreadingHTTPServer(address or (profile.host, profile.port), Handler)
    server.daemon_threads = True
    return server

def serve(store, profile_id):
    from .adapters import get_adapter
    profile = store.get_profile(profile_id)
    module = load_binding(get_adapter(profile.runtime_id).runtime_dir(store))
    # No listener is exposed until the model and session are actually initialized.
    from .runtime_paths import ascii_model_path
    with module.Model(str(ascii_model_path(store.path(profile.model_path))), backend=profile.backend) as model:
        with model.session(**profile.runtime_options.get('session', {})) as session:
            server = make_server(profile, session)
            try: server.serve_forever()
            finally: server.server_close()

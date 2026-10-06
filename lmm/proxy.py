from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
from email.parser import BytesParser
from email.policy import default

import httpx

ASR_ALIAS = 'local-asr'

def route_asr_alias(body, content_type, model_id):
    """Only the explicit gateway alias is routed; other IDs retain engine semantics."""
    if not content_type.lower().startswith('multipart/form-data'): return body, content_type
    message = BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
    parts = list(message.iter_parts())
    models = [p for p in parts if p.get_param('name',header='content-disposition')=='model' and p.get_filename() is None]
    if len(models)!=1 or models[0].get_payload(decode=True)!=ASR_ALIAS.encode(): return body, content_type
    files=[]
    for part in parts:
        name=part.get_param('name',header='content-disposition')
        if not name: raise ValueError('Multipart field has no name')
        data=model_id.encode() if part is models[0] else part.get_payload(decode=True)
        files.append((name,(part.get_filename(),data,part.get_content_type())))
    request=httpx.Request('POST','http://localhost',files=files)
    return request.read(), request.headers['content-type']


def clean_text(text: str) -> str:
    return re.sub(r"^language [^<\r\n]{1,80}<asr_text>", "", text, count=1)


class APIGateway:
    def __init__(self, port, upstream_port, upstream_host="127.0.0.1", strip_prefix=False, asr_model_id=None):
        host = "127.0.0.1" if upstream_host in {"0.0.0.0", "localhost"} else upstream_host
        if host == "::": host = "::1"
        if ":" in host: host = f"[{host}]"
        upstream = f"http://{host}:{upstream_port}"
        self.client = client = httpx.Client(timeout=httpx.Timeout(180, connect=5), trust_env=False)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self): self.forward()
            def do_POST(self): self.forward()
            def forward(self):
                paths = {"/health", "/v1/models"} if self.command=="GET" else {"/v1/audio/transcriptions", "/audio/transcriptions", "/v1/chat/completions", "/v1/embeddings", "/v1/rerank", "/v1/audio/speech"}
                if self.path not in paths: self.send_error(404); return
                self.connection.settimeout(30)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if self.command == "POST" and (length <= 0 or length > 128*1024**2): self.send_error(413); return
                    if self.headers.get("Transfer-Encoding"): self.send_error(411); return
                    body = self.rfile.read(length) if length else b""
                    if len(body) != length: self.send_error(400); return
                    headers = {k: v for k,v in self.headers.items() if k.lower() in {"content-type", "authorization", "accept"}}
                    if asr_model_id and self.command=='POST' and self.path.endswith('/audio/transcriptions'):
                        body,content_type=route_asr_alias(body,self.headers.get('Content-Type',''),asr_model_id)
                        headers={k:v for k,v in headers.items() if k.lower()!='content-type'}
                        headers['Content-Type']=content_type
                    response = client.request(self.command, upstream+self.path, headers=headers, content=body)
                    content = response.content
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    if asr_model_id and self.path=='/v1/models' and response.is_success:
                        data=response.json()
                        if isinstance(data.get('data'),list) and not any(m.get('id')==ASR_ALIAS for m in data['data']):
                            data['data'].append({'id':ASR_ALIAS,'object':'model','owned_by':'local-model-manager'})
                            content=json.dumps(data,ensure_ascii=False).encode()
                    if strip_prefix and response.is_success and self.path.endswith('/audio/transcriptions'):
                        try:
                            data = response.json()
                            if isinstance(data, dict) and isinstance(data.get("text"), str):
                                cleaned = clean_text(data["text"])
                                if cleaned != data["text"]:
                                    data["text"] = cleaned
                                    content = json.dumps(data, ensure_ascii=False).encode("utf-8")
                        except ValueError: pass
                    self.send_response(response.status_code)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content))); self.end_headers(); self.wfile.write(content)
                except (httpx.HTTPError, OSError, ValueError):
                    self.send_error(502, "Upstream request failed")
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="asr-proxy"); self.thread.start()

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.client.close()

class CompatibilityProxy(APIGateway):
    def __init__(self, port, upstream_port, upstream_host='127.0.0.1', asr_model_id=None):
        super().__init__(port, upstream_port, upstream_host, strip_prefix=True, asr_model_id=asr_model_id)

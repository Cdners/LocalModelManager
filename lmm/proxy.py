from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading

import httpx


def clean_text(text: str) -> str:
    return re.sub(r"^language [^<\r\n]{1,80}<asr_text>", "", text, count=1)


class CompatibilityProxy:
    def __init__(self, port, upstream_port, upstream_host="127.0.0.1"):
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
                paths = {"/health", "/v1/models"} if self.command=="GET" else {"/v1/audio/transcriptions", "/audio/transcriptions"}
                if self.path not in paths: self.send_error(404); return
                self.connection.settimeout(30)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if self.command == "POST" and (length <= 0 or length > 128*1024**2): self.send_error(413); return
                    if self.headers.get("Transfer-Encoding"): self.send_error(411); return
                    body = self.rfile.read(length) if length else b""
                    if len(body) != length: self.send_error(400); return
                    headers = {k: v for k,v in self.headers.items() if k.lower() in {"content-type", "authorization", "accept"}}
                    response = client.request(self.command, upstream+self.path, headers=headers, content=body)
                    content = response.content
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    if response.is_success and self.command=="POST":
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

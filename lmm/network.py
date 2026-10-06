"""One explicit proxy policy for metadata and downloads. Never applied to local inference."""
from __future__ import annotations
import base64
import socket
import ssl
import uuid
from urllib.parse import urlsplit, unquote, quote
from urllib.request import getproxies, proxy_bypass
import httpx
import truststore
from .config import atomic_json, read_json

MODES = ('direct', 'system', 'http', 'https', 'socks5', 'socks5h')
_store = None

def safe_error(error):
    import re
    text=str(error)
    return re.sub(r'([a-zA-Z][a-zA-Z0-9+.-]*://)[^/@\s]+@',r'\1[redacted]@',text)

def configure(store):
    global _store
    _store = store

def parse_proxy(value):
    data = dict(value or {'mode': 'system'})
    mode = data.get('mode', 'system')
    raw = data.pop('url', '').strip()
    if raw:
        parsed = urlsplit(raw)
        mode = parsed.scheme.lower()
        if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('Proxy URL must not contain a path, query or fragment.')
        try: port = parsed.port
        except ValueError: raise ValueError('Invalid proxy port.') from None
        data.update(host=parsed.hostname or '', port=port,
                    username=unquote(parsed.username or ''), password=unquote(parsed.password or ''))
    if mode not in MODES: raise ValueError('Unsupported proxy mode.')
    if mode in ('direct', 'system'): return {'mode': mode}
    host = str(data.get('host', '')).strip()
    if not host or any(c.isspace() for c in host) or any(c in host for c in '/@?#'):
        raise ValueError('Enter a proxy host without a path.')
    try: port = int(data.get('port') or 0)
    except (ValueError, TypeError): raise ValueError('Invalid proxy port.') from None
    if not 1 <= port <= 65535: raise ValueError('Proxy port must be between 1 and 65535.')
    return {'mode': mode, 'host': host, 'port': port, 'username': str(data.get('username', '')),
            'password': str(data.get('password', '')), 'credential_id': data.get('credential_id', '')}

def save_proxy(store, value):
    data = parse_proxy(value)
    password = data.pop('password', '')
    if password:
        from .windows import protect
        path = store.config / 'proxy_credentials.json'
        values = read_json(path, {})
        identity = uuid.uuid4().hex
        values[identity] = base64.b64encode(protect(password.encode())).decode()
        atomic_json(path, values)
        data['credential_id'] = identity
    return data

def resolve(value=None, store=None):
    store = store or _store
    if not value or value.get('mode') == 'global':
        value = store.settings.get('download_proxy', {'mode': 'system'}) if store else {'mode': 'system'}
    data = parse_proxy(value)
    if data.get('credential_id') and not data.get('password'):
        if store is None: raise ValueError('Proxy credential store is unavailable.')
        from .windows import protect
        encoded = read_json(store.config / 'proxy_credentials.json', {}).get(data['credential_id'])
        if not encoded: raise ValueError('Saved proxy credentials are unavailable.')
        data['password'] = protect(base64.b64decode(encoded), True).decode()
    return data

def proxy_url(data):
    host = data['host']
    if ':' in host: host = '[' + host.strip('[]') + ']'
    auth = ''
    if data.get('username') or data.get('password'):
        auth = quote(data.get('username', ''), safe='') + ':' + quote(data.get('password', ''), safe='') + '@'
    return f"{data['mode']}://{auth}{host}:{data['port']}"

class ProxyTransport(httpx.BaseTransport):
    def __init__(self, policy):
        self.policy = policy
        self.transports = {}
        self.verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def handle_request(self, request):
        mode = self.policy['mode']
        proxy = None
        if mode == 'system':
            if not proxy_bypass(request.url.host):
                proxies = getproxies()
                proxy = proxies.get(request.url.scheme) or proxies.get('all')
        elif mode != 'direct': proxy = proxy_url(self.policy)
        transport = self.transports.get(proxy)
        if transport is None:
            transport = httpx.HTTPTransport(proxy=proxy, verify=self.verify, trust_env=False)
            self.transports[proxy] = transport
        # httpcore sends SOCKS host names remotely by default. SOCKS5 explicitly
        # resolves locally; SOCKS5H keeps the original host for remote DNS.
        if mode == 'socks5':
            address = socket.getaddrinfo(request.url.host, request.url.port or 443, type=socket.SOCK_STREAM)[0][4][0]
            request = httpx.Request(request.method, request.url.copy_with(host=address),
                headers=request.headers, stream=request.stream,
                extensions=request.extensions | {'sni_hostname': request.url.host})
        return transport.handle_request(request)

    def close(self):
        for transport in self.transports.values(): transport.close()

def client_options(value=None):
    return {'transport': ProxyTransport(resolve(value)), 'trust_env': False}

def test_connection(value, url):
    with httpx.Client(**client_options(value), timeout=15, follow_redirects=True) as session:
        try:
            response = session.get(url)
            if response.status_code >= 400: raise ValueError(f'Connection test: HTTP {response.status_code}')
            return f'{urlsplit(url).hostname}: HTTP {response.status_code}'
        except httpx.HTTPError as exc:
            raise ValueError('Connection test failed: ' + type(exc).__name__) from None

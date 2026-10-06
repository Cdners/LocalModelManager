import hashlib
import json
import socket
from pathlib import Path
import httpx
import pytest
from lmm.config import Store
from lmm.network import parse_proxy,save_proxy,resolve,ProxyTransport
from lmm.net import DownloadManager
from lmm.jobs import Control

@pytest.mark.parametrize('scheme',['http','https','socks5','socks5h'])
def test_standard_proxy_urls_and_encrypted_credentials(tmp_path,scheme):
    store=Store(tmp_path)
    config=save_proxy(store,{'url':scheme+'://user:p%40ss@127.0.0.1:7891'})
    assert config['mode']==scheme and 'password' not in config
    assert 'p@ss' not in (store.config/'proxy_credentials.json').read_text()
    assert resolve(config,store)['password']=='p@ss'
    assert parse_proxy({'mode':'direct'})=={'mode':'direct'}

def test_socks_dns_policy_and_no_env_proxy(monkeypatch):
    calls=[]
    class Transport:
        def __init__(self,**kw):calls.append(kw)
        def handle_request(self,request):calls.append((request.url.host,request.extensions.get('sni_hostname'),request.headers['host']));return httpx.Response(200)
        def close(self):pass
    monkeypatch.setattr(httpx,'HTTPTransport',Transport)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('203.0.113.3',443))])
    for mode in ['socks5','socks5h','direct']:
        t=ProxyTransport(parse_proxy({'mode':mode,'host':'127.0.0.1','port':7891}))
        t.handle_request(httpx.Request('GET','https://example.test/file'));t.close()
    assert calls[1]==('203.0.113.3','example.test','example.test')
    assert calls[3]==('example.test',None,'example.test')
    assert calls[4]['proxy'] is None and calls[4]['trust_env'] is False

def test_disconnect_resumes_from_written_offset(tmp_path):
    data=b'a'*65536+b'b'*65536
    ranges=[]
    class Broken(httpx.SyncByteStream):
        def __iter__(self):yield data[:65536];raise httpx.ReadError('disconnect')
    def respond(request):
        ranges.append(request.headers.get('range'))
        if len(ranges)==1:return httpx.Response(200,headers={'Content-Length':str(len(data)),'ETag':'"fixed"'},stream=Broken())
        assert request.headers['if-range']=='"fixed"'
        return httpx.Response(206,headers={'Content-Range':f'bytes 65536-{len(data)-1}/{len(data)}','ETag':'"fixed"'},content=data[65536:])
    control=Control();control.wait=lambda _:None
    target=tmp_path/'model.gguf'
    result=DownloadManager(lambda:httpx.Client(transport=httpx.MockTransport(respond))).download('https://example.test/model',target,control,expected_size=len(data),expected_sha=hashlib.sha256(data).hexdigest())
    assert ranges==[None,'bytes=65536-'] and target.read_bytes()==data
    assert result['sha256']==hashlib.sha256(data).hexdigest()

def test_range_ignored_preserves_partial_and_task_proxy(tmp_path,monkeypatch):
    import lmm.net as net
    target=tmp_path/'model';partial=tmp_path/'model.part';partial.write_bytes(b'abcd')
    selected=[]
    def factory(network=None):
        selected.append(network)
        return httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'abcdefgh')))
    monkeypatch.setattr(net,'client',factory)
    control=Control(network={'mode':'direct'})
    with pytest.raises(ValueError,match='Range'):DownloadManager().download('https://example.test/model',target,control,expected_size=8)
    assert partial.read_bytes()==b'abcd' and not target.exists() and selected==[{'mode':'direct'}]

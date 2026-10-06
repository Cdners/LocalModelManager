from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading
import httpx
from lmm.proxy import CompatibilityProxy,route_asr_alias
from lmm.api import connection_model_id
from lmm.config import Profile

def test_stable_alias_routes_to_each_runtime_without_changing_audio():
    captured=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            body=json.dumps({'data':[{'id':'engine-id'}]}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\n\r\n').encode()+body)
            values={p.get_param('name',header='content-disposition'):p.get_payload(decode=True) for p in message.iter_parts()}
            captured.append(values)
            result=b'{"text":"ok"}'
            self.send_response(200);self.send_header('Content-Length',str(len(result)));self.end_headers();self.wfile.write(result)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    audio=b'RIFF\x00\xff\xfe\r\nmodel=local-asr\x80'
    try:
        for engine in ('qwen-id','audio-fun-id','transcribe-fun-id'):
            proxy=CompatibilityProxy(0,server.server_port,asr_model_id=engine);proxy.start()
            try:
                with httpx.Client(trust_env=False) as c:
                    url='http://127.0.0.1:'+str(proxy.server.server_port)
                    assert 'local-asr' in [m['id'] for m in c.get(url+'/v1/models').json()['data']]
                    r=c.post(url+'/v1/audio/transcriptions',data={'model':'local-asr','language':'zh'},files={'file':('clip.wav',audio,'audio/wav')})
                    assert r.json()['text']=='ok'
                    assert captured[-1]=={'model':engine.encode(),'language':b'zh','file':audio}
            finally:proxy.stop()
    finally:server.shutdown();server.server_close();thread.join()
    request=httpx.Request('POST','http://localhost',data={'model':'explicit-other-id'},files={'file':('clip.wav',audio)})
    body=request.read();ctype=request.headers['content-type']
    assert route_asr_alias(body,ctype,'engine-id')==(body,ctype)
    assert connection_model_id(Profile('x','X',compatibility_proxy=True),['engine-id'])=='local-asr'
    assert connection_model_id(Profile('x','X'),['engine-id'])=='engine-id'

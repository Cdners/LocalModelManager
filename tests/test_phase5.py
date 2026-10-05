import json
import wave

import httpx
import pytest

from lmm.api import model_ids, parse_transcription, snapshot
from lmm.audio import write_wav
from lmm.config import Profile
from lmm.proxy import clean_text


def test_openai_parsing_and_route_readiness():
    assert model_ids({"data":[{"id":"actual-server-id"}]}) == ["actual-server-id"]
    with pytest.raises(ValueError): model_ids({"data":[]})
    with pytest.raises(ValueError): parse_transcription(httpx.Response(200, json={"wrong":"field"}))
    def respond(req):
        if req.url.path == "/health": return httpx.Response(200, json={"status":"ok"})
        if req.url.path == "/v1/models": return httpx.Response(200, json={"data":[{"id":"actual"}]})
        return httpx.Response(400, json={"error":"missing file"})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result=snapshot(Profile("test","test"), client)
    assert result["state"]=="READY" and result["model_ids"]==["actual"]


def test_prefix_removal_preserves_recognized_content():
    assert clean_text("language Chinese<asr_text> 我准备修改 FastAPI。") == " 我准备修改 FastAPI。"
    for text in ["language Chinese", "前文 language Chinese<asr_text>正文", "普通中文", "<asr_text>正文"]:
        assert clean_text(text)==text


def test_microphone_conversion(tmp_path):
    path=tmp_path/"test.wav"
    result=write_wav(bytes(48000*2*2),48000,2,"Int16",path)
    with wave.open(str(path),"rb") as wav:
        assert (wav.getnchannels(),wav.getframerate(),wav.getsampwidth())==(1,16000,2)
        assert abs(wav.getnframes()/16000-1)<.001
    assert result["silence"]

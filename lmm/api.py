from __future__ import annotations

import json
import time
import wave
from pathlib import Path

import httpx

from .config import Profile
from .jobs import Control


def base_url(profile: Profile, proxy=False):
    host = profile.host
    if host in {"0.0.0.0", "localhost"}: host = "127.0.0.1"
    if host == "::": host = "::1"
    if proxy and profile.compatibility_proxy: return f"http://127.0.0.1:{profile.proxy_port}/v1"
    if ":" in host: host = f"[{host}]"
    return f"http://{host}:{profile.port}/v1"


def model_ids(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("/v1/models did not return an OpenAI model list.")
    ids = [item["id"] for item in data["data"] if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]]
    if not ids: raise ValueError("The server has not exposed a model ID yet.")
    return ids

def connection_model_id(profile, ids):
    if not ids:return ''
    if profile.type=='asr' and profile.compatibility_proxy:
        from .proxy import ASR_ALIAS
        return ASR_ALIAS
    return ids[0]


def parse_transcription(response: httpx.Response):
    if not response.is_success:
        raise ValueError(f"Transcription HTTP {response.status_code}: {response.text[:1500]}")
    try: data = response.json()
    except ValueError as exc: raise ValueError("Transcription response is not JSON.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        raise ValueError("Transcription JSON is missing its text field.")
    return data


def snapshot(profile: Profile, session=None):
    result = {"state": "LOADING MODEL", "health": False, "models": False, "transcription": False, "model_ids": []}
    own = session is None
    session = session or httpx.Client(timeout=httpx.Timeout(3, connect=1), trust_env=False)
    url = base_url(profile)
    try:
        health = session.get(url[:-3]+"/health")
        result["health"] = health.is_success
        models = session.get(url+"/models")
        if models.is_success:
            result["model_ids"] = model_ids(models.json()); result["models"] = True
        if profile.type == "asr" and result["models"]:
            # Deliberately omit audio. Validation errors confirm the route without performing inference.
            probe = session.post(url+"/audio/transcriptions", files={"model": (None, result["model_ids"][0])})
            from .adapters import get_adapter
            result["transcription"] = get_adapter(profile.runtime_id).transcription_route_available(probe)
            result["route_status"] = probe.status_code
        if result["health"] and result["models"] and (profile.type != "asr" or result["transcription"]): result["state"] = "READY"
        if result["models"] and profile.type == "asr" and not result["transcription"]:
            result["detail"] = "Model API is available, but the transcription route is not ready."
    except (httpx.HTTPError, ValueError) as exc:
        result["detail"] = str(exc)
    finally:
        if own: session.close()
    return result


def wait_ready(profile, alive, timeout=240, control=None, progress=lambda _: None):
    control = control or Control()
    deadline = time.monotonic()+timeout
    result = {}
    while time.monotonic() < deadline:
        control.check()
        if not alive(): raise RuntimeError("The managed server exited while loading. See its profile log.")
        result = snapshot(profile); progress(result)
        if result["state"] == "READY": return result
        control.wait(1)
    raise TimeoutError("Server readiness timed out: " + result.get("detail", result.get("state", "unknown")))


def transcribe(profile, audio: Path, control=None, progress=lambda _: None, language=None):
    control = control or Control(); control.check()
    ready = snapshot(profile)
    if not ready["models"]: raise ValueError("The model ID must be read from a ready /v1/models endpoint first.")
    duration = None
    if audio.suffix.lower() == ".wav":
        with wave.open(str(audio), "rb") as wav: duration = wav.getnframes()/wav.getframerate()
    model_id = ready["model_ids"][0]
    fields = {"model": model_id, "response_format": "json"}
    if language: fields["language"] = language
    started = time.perf_counter()
    # Stream the original file. An in-flight HTTP request has a bounded timeout; cancellation
    # takes effect before/after it, rather than claiming a request has been aborted remotely.
    with httpx.Client(timeout=httpx.Timeout(180, connect=5), trust_env=False) as session:
        with audio.open("rb") as handle:
            response = session.post(base_url(profile, proxy=True)+"/audio/transcriptions", data=fields,
                files={"file": (audio.name, handle, "audio/wav" if audio.suffix.lower()==".wav" else "application/octet-stream")})
    elapsed = time.perf_counter()-started
    control.check()
    data = parse_transcription(response)
    result = {"transcript": data["text"], "raw": response.text, "model_id": model_id,
              "audio": str(audio), "audio_duration": duration, "request_seconds": elapsed,
              "rtf": elapsed/duration if duration else None, "http_status": response.status_code}
    progress({"message": f"Transcribed in {elapsed*1000:.0f} ms"})
    return result

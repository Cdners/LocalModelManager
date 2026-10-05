import hashlib
import zipfile

import httpx
import pytest

from lmm.config import Store, atomic_json
from lmm.jobs import Control
from lmm.net import Downloader
from lmm.runtime import Runtime, safe_extract, select_assets


def test_asset_selection_is_cuda_x64_and_pairs_dependencies():
    names = ["llama-b9-bin-win-cpu-x64.zip", "llama-b9-bin-win-cuda-13.4-arm64.zip",
             "llama-b9-bin-win-cuda-12.4-x64.zip", "llama-b9-bin-win-cuda-13.4-x64.zip",
             "cudart-llama-bin-win-cuda-13.4-x64.zip"]
    result = select_assets([{"name": name} for name in names], 13)
    assert [a["name"] for a in result] == names[3:]
    with pytest.raises(ValueError): select_assets([{"name": names[0]}], 13)


def test_resumable_download_and_checksum(tmp_path):
    data = b"abcdefghij"
    target = tmp_path / "model.gguf"
    target.with_name(target.name+".part").write_bytes(data[:4])
    def reply(request):
        assert request.headers["range"] == "bytes=4-"
        return httpx.Response(206, headers={"Content-Range": "bytes 4-9/10"}, content=data[4:])
    factory = lambda: httpx.Client(transport=httpx.MockTransport(reply))
    result = Downloader(factory).download("https://example.test/model", target, Control(), expected_size=10,
        expected_sha=hashlib.sha256(data).hexdigest())
    assert result["size"] == 10 and target.read_bytes() == data
    assert not target.with_name(target.name+".part").exists()


def test_corrupt_download_never_installs(tmp_path):
    factory = lambda: httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"bad")))
    with pytest.raises(ValueError, match="SHA-256"):
        Downloader(factory).download("https://example.test/a", tmp_path/"a", Control(), expected_size=3, expected_sha="0"*64)
    assert not (tmp_path/"a").exists()


def test_zip_traversal_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as f: f.writestr("../escape", "bad")
    with pytest.raises(ValueError): safe_extract(archive, tmp_path/"stage")
    assert not (tmp_path/"escape").exists()


def test_failed_runtime_update_restores_old_files(tmp_path):
    store = Store(tmp_path); runtime = Runtime(store)
    store.runtime.mkdir(parents=True)
    (store.runtime/"llama-server.exe").write_text("old")
    atomic_json(store.runtime/"runtime_info.json", {"version": "old"})
    stage = store.runtime.parent/".llama-stage-test"; stage.mkdir()
    (stage/"llama-server.exe").write_text("new")
    atomic_json(stage/"runtime_info.json", {"version": "new"})
    calls = []
    def health(ids):
        calls.append(ids)
        if len(calls) == 1: raise RuntimeError("new model failed")
    with pytest.raises(RuntimeError, match="restored"):
        runtime.install(stage, Control(), stop=lambda:["qwen"], health=health)
    assert (store.runtime/"llama-server.exe").read_text() == "old"
    assert len(calls) == 2

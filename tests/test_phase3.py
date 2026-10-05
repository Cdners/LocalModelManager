from lmm.models import match_mmproj, model_metadata, Models
from lmm.config import Store, atomic_json
from lmm.jobs import Control


def test_mmproj_exact_and_ambiguous_cases():
    main = "Qwen3-ASR-1.7B-Q8_0.gguf"
    assert match_mmproj(main, [main, "mmproj-"+main]) == "mmproj-"+main
    assert match_mmproj(main, ["mmproj-A-Q8_0.gguf", "mmproj-B-Q8_0.gguf"]) is None
    assert match_mmproj("vision-Q4_K_M.gguf", ["mmproj-F16.gguf"]) == "mmproj-F16.gguf"
    assert match_mmproj(main, ["mmproj-Qwen3-ASR-1.7B-bf16.gguf"]) is None


def test_metadata_pins_commit_and_sha():
    info = model_metadata({"id":"org/model", "sha":"a"*40,
        "siblings":[{"rfilename":"model-Q8.gguf", "lfs":{"size":100, "sha256":"b"*64}}]})
    assert info["revision"] == "a"*40
    assert info["files"][0]["size"] == 100
    assert info["files"][0]["sha256"] == "b"*64


def test_incomplete_model_never_counts_as_installed(tmp_path):
    store=Store(tmp_path); model=store.models/"a.gguf"; model.write_bytes(b"half")
    atomic_json(store.config/"models.json", [{"path":store.relative(model),"size":8}])
    assert Models(store).installed()[0]["valid"] is False


def test_unrelated_repository_commit_is_not_model_update(tmp_path, monkeypatch):
    store=Store(tmp_path); file=store.models/"a.gguf"; file.write_bytes(b"data")
    record={"repo_id":"org/model", "filename":"a.gguf", "path":store.relative(file), "size":4, "sha256":"b"*64,"revision":"a"*40}
    atomic_json(store.config/"models.json",[record])
    models=Models(store)
    monkeypatch.setattr(models,"repository",lambda *args: {"revision":"c"*40,"files":[{"filename":"a.gguf","sha256":"b"*64,"size":4}]})
    assert models.check_updates(Control())[0]["status"] == "Up to date"

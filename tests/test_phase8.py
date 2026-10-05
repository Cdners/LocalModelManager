from pathlib import Path
import pytest

from lmm.config import Store
from lmm.downloads import Downloads
from lmm.updater import newer, parse_manifest, swap_application


def test_version_and_manifest():
    assert newer("v1.10.0","1.9.0")
    assert not newer("1.0.0rc1","1.0.0")
    manifest={"version":"1.0.1","url":"https://example.com/app.zip","sha256":"a"*64}
    assert parse_manifest(manifest)["version"]=="1.0.1"
    with pytest.raises(ValueError):parse_manifest(manifest|{"sha256":"bad"})
    with pytest.raises(ValueError):parse_manifest(manifest|{"url":"http://example.com/app.zip"})


@pytest.mark.parametrize("healthy",[True,False])
def test_app_swap_and_rollback_preserve_model_runtime_config(tmp_path,healthy):
    root=tmp_path
    staging=root/"updates"/"app-stage-test"; staging.mkdir(parents=True)
    for parent,text in [(root,"old"),(staging,"new")]:
        (parent/"LocalModelManager.exe").write_text(text)
        (parent/"app").mkdir(); (parent/"app"/"library.dll").write_text(text)
        (parent/"app_manifest.json").write_text(text)
    for name in ["models","runtime","config","logs","downloads"]:
        (root/name).mkdir(); (root/name/"preserve").write_text(name)
    if healthy:swap_application(root,staging,root/"updates"/"app-backup-test",lambda:True)
    else:
        with pytest.raises(RuntimeError):swap_application(root,staging,root/"updates"/"app-backup-test",lambda:False)
    assert (root/"LocalModelManager.exe").read_text()==("new" if healthy else "old")
    for name in ["models","runtime","config","logs","downloads"]:assert (root/name/"preserve").read_text()==name


def test_downloads_recover_as_paused_without_redownloading(tmp_path):
    store=Store(tmp_path); queue=Downloads(store)
    record=queue.add("model","test",{"revision":"a"*40})
    queue.update(record["id"],{"state":"Running","downloaded":123})
    restored=Downloads(store).records[0]
    assert restored["state"]=="Paused" and restored["downloaded"]==123

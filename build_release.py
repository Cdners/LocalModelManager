"""Build in a disposable build directory; publish only application files into dist."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
import argparse

from lmm import __version__
from lmm.net import sha256


def main():
    root=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(); parser.add_argument("--output-root",type=Path)
    options=parser.parse_args()
    if sys.version_info[:2]!=(3,12):raise RuntimeError("Build requires the project's Python 3.12 environment.")
    os.environ["QT_QPA_PLATFORM"]="offscreen"
    from PySide6.QtWidgets import QApplication
    from lmm.gui import icon
    app=QApplication([])
    assets=root/"build"/"assets"; assets.mkdir(parents=True,exist_ok=True)
    icon().pixmap(256,256).save(str(assets/"manager.ico"))
    build=root/"build"/("package-"+uuid.uuid4().hex[:8])
    # External toolchains (e.g. Poppler's versioned ICU) must never satisfy Qt's
    # Windows-system DLL imports. Scope this environment to the build child only.
    build_env=os.environ.copy()
    windows=Path(os.environ["SystemRoot"])
    build_env["PATH"]=os.pathsep.join([str(Path(sys.executable).parent),str(windows/"System32"),str(windows)])
    build_env["PYINSTALLER_CONFIG_DIR"]=str(root/"build"/"pyinstaller-cache")
    command=[sys.executable,"-m","PyInstaller","--clean","--noconfirm","--onedir","--windowed","--contents-directory","app",
        "--name","LocalModelManager","--icon",str(assets/"manager.ico"),"--add-data",str(root/"assets")+os.pathsep+"assets","--distpath",str(build),"--workpath",str(root/"build"/"pyinstaller"),
        "--specpath",str(root/"build"),"--exclude-module","pytest","--exclude-module","PySide6.QtWebEngineCore",
        "--exclude-module","PySide6.QtWebEngineWidgets","--hidden-import","pynvml",str(root/"main.py")]
    subprocess.run(command,cwd=root,env=build_env,check=True)
    package=build/"LocalModelManager"
    from tools.collect_licenses import collect
    collect(package)
    (package/"app_manifest.json").write_text(json.dumps({"product":"LocalModelManager","version":__version__,"platform":"windows-x64"},indent=2),encoding="utf-8")
    target=(options.output_root or root/"dist"/"LocalModelManager").resolve()
    if not target.is_relative_to(root):raise ValueError("Build output must remain within the project.")
    target.mkdir(parents=True,exist_ok=True)
    # The old app payload is retained for recovery. Runtime/models/config are never touched.
    previous=root/"build"/("previous-app-"+uuid.uuid4().hex[:8]); previous.mkdir()
    moved=[]; installed=[]
    try:
        for name in ("LocalModelManager.exe","app","app_manifest.json"):
            if (target/name).exists():(target/name).rename(previous/name); moved.append(name)
            shutil.move(str(package/name),str(target/name)); installed.append(name)
    except Exception:
        for name in reversed(installed):shutil.move(str(target/name),str(package/name))
        for name in reversed(moved):shutil.move(str(previous/name),str(target/name))
        raise
    archive=root/"dist"/f"LocalModelManager-{__version__}-windows-x64.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=5) as bundle:
        for name in ("LocalModelManager.exe","app","app_manifest.json"):
            path=target/name
            if path.is_dir():
                for file in path.rglob("*"):
                    if file.is_file():bundle.write(file,Path("LocalModelManager")/file.relative_to(target))
            else:bundle.write(path,Path("LocalModelManager")/name)
    digest=sha256(archive)
    archive.with_suffix(".zip.sha256").write_text(digest+"  "+archive.name+"\n",encoding="utf-8")
    print(json.dumps({"exe":str(target/"LocalModelManager.exe"),"zip":str(archive),"sha256":digest},ensure_ascii=False))


if __name__=="__main__":main()

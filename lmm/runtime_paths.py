"""ASCII hard-link views for engines whose Windows file APIs cannot read Unicode."""
import hashlib
import os
from pathlib import Path
import tempfile

def ascii_model_path(path):
    path=Path(path).resolve()
    if os.name!='nt' or str(path).isascii():return path
    stat=path.stat()
    identity=hashlib.sha256((str(path)+str(stat.st_size)+str(stat.st_mtime_ns)).encode()).hexdigest()
    root=Path(tempfile.gettempdir())/'LocalModelManager-model-links'/identity
    if not str(root).isascii():raise ValueError('This runtime needs an ASCII model or temporary directory.')
    root.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
    if len(files)>20000:raise ValueError('Model directory contains too many files.')
    for source in files:
        relative=source.relative_to(path) if path.is_dir() else Path('model'+path.suffix)
        if not str(relative).isascii():raise ValueError('This runtime requires ASCII filenames inside model directories.')
        target=root/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if not os.path.samefile(source,target):raise ValueError('Model link destination does not match the source file.')
        else:
            try:os.link(source,target)
            except OSError:raise ValueError('Cannot create same-volume model link; choose an ASCII model directory for this runtime.') from None
    return root if path.is_dir() else root/('model'+path.suffix)

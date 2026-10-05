from types import SimpleNamespace
from lmm.gpu import Monitor


def test_gpu_fallback_and_unavailable(monkeypatch):
    monitor=Monitor(); monitor.nvml=object()
    monkeypatch.setattr(monitor,"smi",lambda:{"available":True,"source":"nvidia-smi"})
    assert monitor.sample()["source"]=="nvidia-smi"
    def fail(): raise OSError("not installed")
    monkeypatch.setattr(monitor,"smi",fail)
    assert monitor.sample()=={"available":False,"error":"not installed"}


def test_smi_units(monkeypatch):
    monkeypatch.setattr("lmm.gpu.subprocess.run",lambda *a,**kw:SimpleNamespace(stdout="RTX 5060, 12, 2048, 8192, 45, 55.4\n"))
    result=Monitor.smi()
    assert result["total"]==8*1024**3 and result["power"]==55.4

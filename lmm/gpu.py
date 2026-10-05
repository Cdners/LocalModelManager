from __future__ import annotations

import csv
import subprocess
import threading


class Monitor:
    def __init__(self):
        self.nvml = None; self.handle = None
        self.lock = threading.Lock()

    def sample(self):
        with self.lock:
            try:
                if self.nvml is None:
                    import pynvml
                    pynvml.nvmlInit()
                    self.nvml = pynvml; self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                n, h = self.nvml, self.handle
                memory = n.nvmlDeviceGetMemoryInfo(h)
                name=n.nvmlDeviceGetName(h)
                def optional(function):
                    try: return function()
                    except n.NVMLError: return None
                return {"available": True, "source": "NVML", "name": name.decode() if isinstance(name,bytes) else name,
                    "used": memory.used, "total": memory.total,
                    "load": optional(lambda:n.nvmlDeviceGetUtilizationRates(h).gpu),
                    "temperature": optional(lambda:n.nvmlDeviceGetTemperature(h,n.NVML_TEMPERATURE_GPU)),
                    "power": optional(lambda:n.nvmlDeviceGetPowerUsage(h)/1000)}
            except Exception:
                try: return self.smi()
                except Exception as exc: return {"available":False,"error":str(exc)}

    @staticmethod
    def smi():
        result=subprocess.run(["nvidia-smi","--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"], capture_output=True,text=True,timeout=3,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),check=True)
        row=next(csv.reader(result.stdout.splitlines()))
        def number(index):
            try:return float(row[index].strip())
            except ValueError:return None
        return {"available":True,"source":"nvidia-smi","name":row[0].strip(),"load":number(1),
                "used":number(2)*1024**2 if number(2) is not None else None,
                "total":number(3)*1024**2 if number(3) is not None else None,
                "temperature":number(4),"power":number(5)}

    def close(self):
        with self.lock:
            if self.nvml:
                try:self.nvml.nvmlShutdown()
                except Exception:pass
                self.nvml=None

from __future__ import annotations

import array
import audioop
import math
import wave
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


def write_wav(raw: bytes, rate: int, channels: int, sample_format: str, path: Path):
    if sample_format == "Float":
        samples = array.array("f"); samples.frombytes(raw[:len(raw)//4*4])
        raw = array.array("h", [round(max(-1., min(1., v if math.isfinite(v) else 0.))*32767) for v in samples]).tobytes()
    elif sample_format == "UInt8": raw = audioop.lin2lin(audioop.bias(raw, 1, -128), 1, 2)
    elif sample_format == "Int32": raw = audioop.lin2lin(raw, 4, 2)
    elif sample_format != "Int16": raise ValueError("Unsupported microphone PCM format.")
    frame = 2*channels; raw = raw[:len(raw)//frame*frame]
    if channels == 2: raw = audioop.tomono(raw, 2, .5, .5)
    elif channels != 1: raise ValueError("Please select a mono or stereo microphone.")
    if rate != 16000: raw, _ = audioop.ratecv(raw, 2, 1, rate, 16000, None)
    if len(raw) < 3200: raise ValueError("录音太短或未收到麦克风音频。")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(raw)
    rms = audioop.rms(raw, 2)
    return {"path": str(path), "duration": len(raw)/32000, "rms": rms, "silence": rms < 40}


class Recorder(QObject):
    limit_reached = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source = None
        self.limit = QTimer(self); self.limit.setSingleShot(True); self.limit.timeout.connect(self.limit_reached)

    def start(self, device=None):
        if self.source: raise ValueError("A recording is already active.")
        device = device or QMediaDevices.defaultAudioInput()
        if device.isNull(): raise ValueError("未发现麦克风。请在 Windows 声音设置中选择输入设备。")
        fmt = QAudioFormat(); fmt.setSampleRate(16000); fmt.setChannelCount(1); fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt): fmt = device.preferredFormat()
        if fmt.channelCount() not in {1,2}: raise ValueError("请选择单声道或双声道麦克风。")
        self.fmt = (fmt.sampleRate(), fmt.channelCount(), fmt.sampleFormat().name)
        self.buffer = QBuffer(self); self.buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        self.source = QAudioSource(device, fmt, self); self.source.start(self.buffer)
        self.limit.start(300_000)

    def stop(self):
        if not self.source: raise ValueError("Not recording.")
        self.limit.stop(); self.source.stop()
        raw = bytes(self.buffer.data()); self.buffer.close(); self.buffer.deleteLater()
        self.source.deleteLater(); self.source = None
        return (raw, *self.fmt)

"""Pulsar'ın sesini çalma (24 kHz PCM16). Gelen parçalar bir tampona yazılıyor, ses kartı callback'i oradan çekiyor.

play=False ise ses çalınmıyor ama süre yine hesaplanıyor: "cevap ne zaman bitti" bilgisi takip penceresi için lazım.
"""
import threading
import time
import wave
from pathlib import Path

OUT_SR = 24000


class Player:
    def __init__(self, play: bool, device=None, save_dir: str | None = None):
        self.buf = bytearray()
        self.lock = threading.Lock()
        self.end_wall = 0.0   # kuyruktaki sesin çalınıp biteceği an (time.monotonic)
        self.reply = bytearray()
        self.save_dir = Path(save_dir) if save_dir else None
        self.n = 0
        self.stream = None
        if play:
            import sounddevice as sd
            self.stream = sd.RawOutputStream(samplerate=OUT_SR, channels=1, dtype="int16", device=device,
                                             callback=self._cb)
            self.stream.start()

    def write(self, data: bytes) -> None:
        with self.lock:
            if self.stream:
                self.buf += data
            self.reply += data
            self.end_wall = max(self.end_wall, time.monotonic()) + len(data) / 2 / OUT_SR

    def finish_reply(self) -> float:
        """Cevap bitti: sesi kaydet, süresini (sn) döndür."""
        with self.lock:
            audio, self.reply = bytes(self.reply), bytearray()
        if self.save_dir and audio:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.save_dir / f"reply_{self.n:02d}.wav"), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(OUT_SR), w.writeframes(audio)
            self.n += 1
        return len(audio) / 2 / OUT_SR

    def _cb(self, outdata, frames, t, status):
        n = frames * 2
        with self.lock:
            chunk = bytes(self.buf[:n])
            del self.buf[:n]
        outdata[:len(chunk)] = chunk
        if len(chunk) < n:
            outdata[len(chunk):] = b"\x00" * (n - len(chunk))

"""Ses girişi. Şimdilik sadece replay: bir WAV dosyasını mikrofonmuş gibi blok blok besler.

Canlı mikrofon geldiğinde (sounddevice) aynı kuyruğa aynı biçimde (zaman, blok) yazacak; kodun geri kalanı
farkı bilmeyecek (MIMARI §5.1, K14).
"""
import asyncio
import time

import numpy as np
import soundfile as sf

from . import BLOCK, SR


def load_wav(path: str, start_s: float = 0.0, max_s: float | None = None) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32")
    if sr != SR:
        raise ValueError(f"{path}: {sr} Hz, {SR} Hz bekleniyordu")
    if audio.ndim > 1:  # stereo ise mono'ya indir
        audio = audio.mean(axis=1)
    a = int(start_s * SR)
    b = None if max_s is None else a + int(max_s * SR)
    return audio[a:b]


async def replay(audio: np.ndarray, q: asyncio.Queue, start_s: float = 0.0, speed: float = 1.0) -> None:
    """`audio`'yu 512 örneklik bloklar halinde kuyruğa yazar: (medya_zamanı_sn, blok).

    speed=1 → gerçek zaman (32 ms'de bir blok), speed=4 → 4 kat hızlı, speed=0 → bekleme yok (ölçüm için).
    Sonda `None` yazar (akış bitti).
    """
    t0 = time.monotonic()
    for i in range(0, len(audio) - BLOCK + 1, BLOCK):
        if speed > 0:
            delay = t0 + (i / SR) / speed - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
        elif i % (BLOCK * 32) == 0:
            await asyncio.sleep(0)  # hızlı modda diğer görevlere de sıra ver
        await q.put((start_s + i / SR, audio[i:i + BLOCK]))
    await q.put(None)

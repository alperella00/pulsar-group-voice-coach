"""Konuşmacı tanıma: ses parmak izi (MIMARI §5.4, K9, K10, K18).

kayıt:  ses → 2 sn pencereler (1 sn kaydırarak) → her biri 256'lık vektör → normalize → ortalama → normalize = profil
tanıma: tur sesi → 256'lık vektör → her profille kosinüs → en_iyi ≥ τ ve en_iyi − ikinci ≥ m ise isim, değilse unknown
"""
from dataclasses import dataclass

import numpy as np
import sherpa_onnx

from . import SR

MODEL = "models/wespeaker_en_voxceleb_resnet34_LM.onnx"
WIN_S, HOP_S = 2.0, 1.0
MAX_TURN_S = 8.0  # uzun turun ilk 8 sn'si yeter (ölçümlerdeki "doğal tur" ile aynı sınır)


@dataclass
class Result:
    name: str | None      # None = unknown
    best_name: str        # eşikten bağımsız en benzer profil
    best: float
    margin: float         # en_iyi − ikinci
    scores: dict[str, float]


class SpeakerID:
    def __init__(self, tau: float = 0.45, margin: float = 0.05, model: str = MODEL):
        self.ext = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=2))
        self.tau, self.m = tau, margin
        self.names: list[str] = []
        self.C = np.zeros((0, 256), np.float32)  # profiller: kişi sayısı × 256

    def embed(self, x: np.ndarray) -> np.ndarray:
        s = self.ext.create_stream()
        s.accept_waveform(SR, x)
        s.input_finished()
        v = np.asarray(self.ext.compute(s), dtype=np.float32)
        return v / np.linalg.norm(v)

    def enroll(self, name: str, audio: np.ndarray) -> int:
        """Kişiyi kaydeder, kaç pencereden profil çıktığını döner."""
        size, step = int(WIN_S * SR), int(HOP_S * SR)
        if len(audio) < size:
            audio = np.pad(audio, (0, size - len(audio)))
        ch = np.stack([self.embed(audio[i:i + size]) for i in range(0, len(audio) - size + 1, step)])
        c = ch.mean(0)
        c /= np.linalg.norm(c)
        self.names.append(name)
        self.C = np.vstack([self.C, c])
        return len(ch)

    def identify(self, audio: np.ndarray) -> Result:
        e = self.embed(audio[: int(MAX_TURN_S * SR)])
        s = self.C @ e                      # bütün karşılaştırmalar tek matris çarpımı
        order = np.argsort(s)[::-1]
        best = float(s[order[0]])
        second = float(s[order[1]]) if len(s) > 1 else -1.0
        ok = best >= self.tau and best - second >= self.m
        name = self.names[order[0]]
        return Result(name if ok else None, name, round(best, 3), round(best - second, 3),
                      {n: round(float(v), 3) for n, v in zip(self.names, s)})

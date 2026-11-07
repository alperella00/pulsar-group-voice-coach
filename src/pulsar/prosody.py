"""Prosodi: kişi NASIL konuşuyor? (MIMARI §5.5, K6, K8)

Her tur için (ASR kelime zamanlarından + sesten):
  rate       konuşma hızı: hece / konuşma süresi (sn). Hece sayısı pyphen ile (İngilizce heceleme sözlüğü).
  pauses     tur içinde kelimeler arası ≥ 250 ms boşluk sayısı (250 ms literatürde önerilen eşik)
  pause_ms   bu boşlukların ortalama süresi
  mlr        mean length of run: iki duraksama arasındaki ortalama hece (akıcılığın güçlü göstergelerinden)
  fillers    "uh, um, er, hmm" sayısı (ASR bunları yazıyor)
  f0         pitch medyanı (Hz), Praat'ın otokorelasyon yöntemi (parselmouth)

Kişinin "normali" tanıtımdan çıkıyor: tanıtım ~5 sn'lik parçalara bölünüp her parçada ölçülüyor → ortalama ve
standart sapma. Her yeni turda z = (değer − ortalama) / sapma. Mutlak değer değil kişinin kendi normali (K8).

Durum (sadeleştirilmiş kural; MIMARI'deki "cümle ortası duraksama" sözdizimi gerektirdiği için şimdilik yok):
  sinyaller: yavaş (rate z ≤ −1), kısa koşular (mlr z ≤ −1, sadece turda duraksama varsa), uzun duraksama (pause_ms ≥ 700) ya da dolgu (≥ 2)
  2+ sinyal → struggling, 1 sinyal → slightly_slow, 0 → normal
"""
from dataclasses import dataclass, field

import numpy as np
import parselmouth
import pyphen

from . import SR
from .asr import Word

PAUSE_S = 0.25
FILLERS = {"uh", "um", "er", "erm", "hmm", "mm", "uhm"}
_dic = pyphen.Pyphen(lang="en_US")
# sapma tabanı: tanıtım kısa olduğu için sapma çok küçük çıkıp z'yi şişirmesin
SD_FLOOR = {"rate": 0.4, "mlr": 1.5, "pause_ms": 120.0, "f0": 10.0}


def syllables(word: str) -> int:
    w = "".join(c for c in word.lower() if c.isalpha())
    return max(1, len(_dic.inserted(w).split("-"))) if w else 0


@dataclass
class Features:
    rate: float
    pauses: int
    pause_ms: float
    mlr: float
    fillers: int
    f0: float | None
    z: dict = field(default_factory=dict)
    state: str = "normal"
    signals: list = field(default_factory=list)


def measure(words: list[Word], audio: np.ndarray | None = None) -> Features | None:
    ws = [w for w in words if any(c.isalpha() for c in w.text)]
    if len(ws) < 3:
        return None
    syl = [syllables(w.text) for w in ws]
    gaps = [b.start - a.end for a, b in zip(ws, ws[1:])]
    pauses = [g for g in gaps if g >= PAUSE_S]
    speak_s = max(ws[-1].end - ws[0].start - sum(pauses), 0.3)
    runs, cur = [], syl[0]
    for g, s in zip(gaps, syl[1:]):
        if g >= PAUSE_S:
            runs.append(cur)
            cur = 0
        cur += s
    runs.append(cur)
    f0 = None
    if audio is not None and len(audio) > SR // 2:
        p = parselmouth.Sound(audio.astype(np.float64), SR).to_pitch_ac(pitch_floor=75, pitch_ceiling=500)
        v = p.selected_array["frequency"]
        v = v[v > 0]
        f0 = float(np.median(v)) if len(v) else None
    fill = sum(1 for w in ws if w.text.lower().strip(",.?!") in FILLERS)
    return Features(rate=sum(syl) / speak_s, pauses=len(pauses),
                    pause_ms=1000 * float(np.mean(pauses)) if pauses else 0.0,
                    mlr=float(np.mean(runs)), fillers=fill, f0=f0)


class Baseline:
    """Kişinin tanıtımdaki normali (ortalama, sapma)."""

    def __init__(self, words: list[Word], audio: np.ndarray, chunk_s: float = 5.0):
        rows = []
        end = words[-1].end if words else 0
        t = 0.0
        while t < end:
            ws = [w for w in words if t <= w.start < t + chunk_s]
            f = measure(ws, audio[int(t * SR):int((t + chunk_s) * SR)])
            if f:
                rows.append(f)
            t += chunk_s
        self.n = len(rows)
        self.stats = {}
        for k in ("rate", "mlr", "pause_ms", "f0"):
            v = np.array([getattr(r, k) for r in rows if getattr(r, k) is not None], float)
            if k == "pause_ms":
                v = v[v > 0] if (v > 0).any() else v
            if len(v):
                self.stats[k] = (float(v.mean()), max(float(v.std()), SD_FLOOR[k]))

    def assess(self, f: Features) -> Features:
        for k, (mu, sd) in self.stats.items():
            val = getattr(f, k)
            if val is not None and not (k == "pause_ms" and val == 0):
                f.z[k] = round((val - mu) / sd, 2)
        sig = []
        if f.z.get("rate", 0) <= -1:
            sig.append("slow")
        # MLR sadece turda duraksama varsa anlamlı: duraksamasız kısa turda MLR = turun toplam hecesi olur ve
        # tanıtımın 5 sn'lik parçalarıyla kıyaslanınca yanlışlıkla "kısa koşu" çıkar (ölçümde böyle oldu)
        if f.pauses >= 1 and f.z.get("mlr", 0) <= -1:
            sig.append("short_runs")
        if f.pause_ms >= 700 or f.fillers >= 2:
            sig.append("long_pauses_or_fillers")
        f.signals = sig
        f.state = "struggling" if len(sig) >= 2 else ("slightly_slow" if sig else "normal")
        return f

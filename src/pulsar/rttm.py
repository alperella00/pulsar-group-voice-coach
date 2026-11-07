"""RTTM okuma ve replay için kayıt aralıklarını seçme.

Canlı demoda kayıt etiketi tanıtım sırasından gelecek ("Ahmet, kendini tanıt"). AMI replay'inde bu etiketi RTTM
veriyor: her kişinin kronolojik ilk temiz (örtüşmesiz) konuşması, min(25 sn, temiz konuşmasının yarısı) kadar.
Bu kural scripts/speaker_id_ami.py ile aynı, böylece sonuçlar karşılaştırılabilir.
"""
from collections import defaultdict

import numpy as np


def load_rttm(path: str) -> list[tuple[float, float, str]]:
    segs = []
    for line in open(path):
        p = line.split()
        segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    return segs


def timeline(segs, total_s: float):
    """10 ms çözünürlükte: her kişi için konuştuğu dilimler + her dilimde kaç kişi konuşuyor."""
    T = int(total_s * 100) + 1
    count = np.zeros(T, np.int16)
    owner = defaultdict(lambda: np.zeros(T, bool))
    for s, e, spk in segs:
        a, b = int(s * 100), min(int(e * 100), T)
        count[a:b] += 1
        owner[spk][a:b] = True
    return dict(owner), count


def runs(mask) -> list[tuple[float, float]]:
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return [(a / 100, b / 100) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0])]


def enrollment_spans(segs, total_s: float, max_s: float = 25.0) -> dict[str, list[tuple[float, float]]]:
    owner, count = timeline(segs, total_s)
    out = {}
    for spk, own in sorted(owner.items()):
        clean = runs(own & (count == 1))
        target = min(max_s, sum(b - a for a, b in clean) / 2)
        spans, acc = [], 0.0
        for a, b in clean:
            take = min(b - a, target - acc)
            spans.append((a, round(a + take, 2)))
            acc += take
            if acc >= target - 1e-6:
                break
        out[spk] = spans
    return out

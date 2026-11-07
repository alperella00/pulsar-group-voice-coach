"""Tur içinde konuşmacı değişimi (K20). VAD sadece konuşma/sessizlik ayırıyor; iki kişi araya 500 ms boşluk
koymadan konuşunca ikisini tek tur yapıyor. Burada turu kimliğe bakarak bölüyoruz. İki mekanizma:

1. Kayan pencereler: 1,5 sn'lik pencereler, 0,5 sn'de bir kayarak. Her pencereye en yakın profilin ismi verilir.
   Yeni isim en az 2 pencere sürerse değişim sayılır (tek pencerelik titreme turu bölmesin).
   Kesim yeri iki pencere merkezinin ortası; yakında (±0,75 sn) bir boşluk varsa boşluğa kaydırılır.

       ses      A A A A A A B B B B B B
       pencere  [A A A]→A  [A A B]→A  [A B B]→B  [B B B]→B
                                    ↑ değişim (~0,5 sn hassasiyet)

2. Aday kesim noktaları: tur içindeki ≥ 150 ms boşluklar. Boşluğun solundaki ve sağındaki ses (en az 1 sn, en
   fazla 3 sn) ayrı ayrı tanınır; iki taraf da net (fark ≥ m) ve farklı kişiyse turu oradan böl.

Bölünen her alt tur kendi sesinin tamamıyla yeniden tanınır. MIN_ID_S'den kısa alt turlara isim verilmez:
1 sn'den kısa seste parmak izi güvenilmez (tek kişilik turlarda bile doğru %34).
Üst üste konuşmayı (iki kişi aynı anda) bu yöntem çözmez; o, hedef konuşmacı çıkarma / TS-VAD işi.
"""
from dataclasses import dataclass

import numpy as np

from . import BLOCK, SR
from .speaker import Result, SpeakerID

WIN_S, HOP_S = 1.5, 0.5
MIN_RUN = 2           # yeni isim en az kaç ardışık pencere sürmeli
GAP_MIN_S = 0.15      # aday kesim noktası için en kısa boşluk
GAP_SIDE_S = (1.0, 3.0)
SNAP_S = 0.75         # pencere sınırı bu kadar yakın bir boşluğa kaydırılır
MERGE_S = 1.0         # birbirine bu kadar yakın kesimler birleştirilir
MIN_ID_S = 1.0        # bundan kısa alt turlara isim verilmez
BLOCK_S = BLOCK / SR


@dataclass
class Piece:
    start: float           # tur başına göre (sn)
    end: float
    result: Result | None  # None = kısa, isim verilmedi


def gaps(probs: np.ndarray, neg_th: float) -> list[float]:
    """Tur içindeki ≥ 150 ms sessizliklerin orta noktaları (tur başına göre sn)."""
    quiet = probs < neg_th
    out, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * BLOCK_S >= GAP_MIN_S and i > 0 and j < len(quiet):
                out.append((i + j) / 2 * BLOCK_S)
            i = j
        else:
            i += 1
    return out


def window_changes(spk: SpeakerID, audio: np.ndarray) -> list[float]:
    size, hop = int(WIN_S * SR), int(HOP_S * SR)
    if len(audio) < size + 2 * hop:
        return []
    E = np.stack([spk.embed(audio[i:i + size]) for i in range(0, len(audio) - size + 1, hop)])
    S = E @ spk.C.T
    top = S.argmax(1)
    srt = np.sort(S, 1)
    clear = (srt[:, -1] - srt[:, -2]) >= spk.m      # net olmayan pencereler kararda yok sayılır
    labels = [int(t) if c else -1 for t, c in zip(top, clear)]
    changes, cur, i = [], None, 0
    while i < len(labels):
        if labels[i] == -1:
            i += 1
            continue
        j = i
        while j < len(labels) and labels[j] in (labels[i], -1):
            j += 1
        run = sum(1 for k in range(i, j) if labels[k] == labels[i])
        if run >= MIN_RUN:
            if cur is not None and labels[i] != cur[0]:
                last_center = cur[1] * HOP_S + WIN_S / 2
                first_center = i * HOP_S + WIN_S / 2
                changes.append((last_center + first_center) / 2)
            last = max(k for k in range(i, j) if labels[k] == labels[i])
            cur = (labels[i], last)
        i = j
    return changes


def gap_changes(spk: SpeakerID, audio: np.ndarray, gap_list: list[float]) -> list[float]:
    out = []
    dur = len(audio) / SR
    lo, hi = GAP_SIDE_S
    for g in gap_list:
        if g < lo or dur - g < lo:
            continue
        left = spk.identify(audio[int(max(g - hi, 0) * SR):int(g * SR)])
        right = spk.identify(audio[int(g * SR):int(min(g + hi, dur) * SR)])
        if left.best_name != right.best_name and left.margin >= spk.m and right.margin >= spk.m:
            out.append(g)
    return out


def split_turn(spk: SpeakerID, audio: np.ndarray, probs: np.ndarray | None, neg_th: float = 0.35) -> tuple[list[Piece], dict]:
    dur = len(audio) / SR
    gl = gaps(probs, neg_th) if probs is not None else []
    wc = window_changes(spk, audio)
    snapped = []
    for c in wc:
        near = [g for g in gl if abs(g - c) <= SNAP_S]
        snapped.append(min(near, key=lambda g: abs(g - c)) if near else c)
    gc = gap_changes(spk, audio, gl)
    cuts = []
    for c in sorted(snapped + gc):
        if c < MIN_ID_S / 2 or dur - c < MIN_ID_S / 2:
            continue
        if cuts and c - cuts[-1] < MERGE_S:
            continue
        cuts.append(c)
    bounds = [0.0] + cuts + [dur]
    pieces = []
    for a, b in zip(bounds, bounds[1:]):
        x = audio[int(a * SR):int(b * SR)]
        pieces.append(Piece(round(a, 3), round(b, 3), spk.identify(x) if b - a >= MIN_ID_S else None))
    info = {"window_cuts": [round(c, 2) for c in wc], "gap_cuts": [round(c, 2) for c in gc],
            "gaps": len(gl), "cuts": [round(c, 2) for c in cuts]}
    return pieces, info

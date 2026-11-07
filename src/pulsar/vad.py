"""VAD ile tur kesme (MIMARI §5.2, K19).

Silero her 32 ms blok için 0-1 arası bir "konuşma olasılığı" veriyor. Turu bu olasılıktan biz kesiyoruz:

  sessizlikte  ── olasılık ≥ eşik ─────────────►  konuşmada (tur başladı)
  konuşmada    ── olasılık < eşik − 0,15, art arda min_silence_ms boyunca ──►  tur bitti

İki ayrı eşik (histerezis): olasılık eşiğin hemen altına inip çıktığında tur titreyip bölünmesin diye.
Turun başına birkaç blok "ön tampon" ekleniyor, çünkü VAD konuşmanın ilk hecesini genelde bir iki blok geç fark ediyor.
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import torch
from silero_vad import load_silero_vad

from . import BLOCK, SR

BLOCK_S = BLOCK / SR  # 0,032 sn


@dataclass
class Turn:
    id: int
    start: float          # medya zamanı (sn): toplantının kaçıncı saniyesi
    end: float
    audio: np.ndarray = field(repr=False)
    end_wall: float = 0.0  # son konuşma bloğunun geldiği an (time.monotonic), gecikme ölçümü için
    probs: np.ndarray = field(default=None, repr=False)  # blok başına Silero olasılığı (tur içi boşlukları bulmak için)

    @property
    def dur(self) -> float:
        return self.end - self.start


class TurnSegmenter:
    def __init__(self, threshold: float = 0.5, min_silence_ms: int = 500, min_turn_ms: int = 250,
                 pad_ms: int = 96, max_turn_s: float = 30.0):
        torch.set_num_threads(1)  # tek blok için çok thread gereksiz; embedding'le CPU kavgası etmesin
        self.model = load_silero_vad()
        self.th, self.neg_th = threshold, max(threshold - 0.15, 0.01)
        self.min_sil = int(min_silence_ms / 1000 / BLOCK_S)   # 500 ms ≈ 16 blok
        self.min_turn_s = min_turn_ms / 1000
        self.max_blocks = int(max_turn_s / BLOCK_S)
        self.pre = deque(maxlen=max(int(pad_ms / 1000 / BLOCK_S), 1))  # ön tampon (son ~96 ms)
        self.in_speech = False
        self.blocks: list[np.ndarray] = []
        self.probs: list[float] = []
        self.pre_p = deque(maxlen=self.pre.maxlen)
        self.start_t = 0.0
        self.silent = 0          # art arda kaç sessiz blok
        self.last_speech_t = 0.0
        self.last_speech_wall = 0.0
        self.next_id = 0
        self.last_prob = 0.0

    def push(self, t: float, block: np.ndarray, wall: float) -> list[tuple]:
        """Bir blok işler. Dönen olaylar: ("start", t) ve/veya ("turn", Turn)."""
        p = self.model(torch.from_numpy(block), SR).item()
        self.last_prob = p
        out = []
        if not self.in_speech:
            if p >= self.th:
                self.in_speech = True
                self.blocks = list(self.pre)
                self.probs = list(self.pre_p)
                self.start_t = t - len(self.pre) * BLOCK_S
                self.silent = 0
                out.append(("start", self.start_t))
            else:
                self.pre.append(block)
                self.pre_p.append(p)
                return out
        self.blocks.append(block)
        self.probs.append(p)
        if p >= self.neg_th:
            self.silent = 0
            self.last_speech_t = t + BLOCK_S
            self.last_speech_wall = wall
        else:
            self.silent += 1
        if self.silent >= self.min_sil or len(self.blocks) >= self.max_blocks:
            turn = self._close()
            if turn:
                out.append(("turn", turn))
        return out

    def flush(self) -> list[tuple]:
        """Akış bitince yarım kalan turu kapatır."""
        if self.in_speech:
            turn = self._close()
            return [("turn", turn)] if turn else []
        return []

    def _close(self) -> Turn | None:
        # sondaki sessiz blokları at, sadece ~96 ms pay bırak
        keep = len(self.blocks) - max(self.silent - self.pre.maxlen, 0)
        audio = np.concatenate(self.blocks[:keep])
        probs = np.array(self.probs[:keep], np.float32)
        self.in_speech, self.blocks, self.probs, self.silent = False, [], [], 0
        self.pre.clear()
        self.pre_p.clear()
        end = self.start_t + len(audio) / SR
        if end - self.start_t < self.min_turn_s:
            return None
        turn = Turn(self.next_id, round(self.start_t, 3), round(end, 3), audio, self.last_speech_wall, probs)
        self.next_id += 1
        return turn

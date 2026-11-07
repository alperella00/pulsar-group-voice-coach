"""ASR: tur sonunda tek seferde yazıya döküm (K3 "C-lite", K11).

Model: parakeet-tdt-0.6b-v3 (MLX, bf16). Ölçüm (scripts/asr_smoke.py, AMI): tur başına medyan ~200 ms,
MLX tepe bellek ~2,0 GB. İlk çağrı ~2 sn (MLX derlemesi) → açılışta warmup().

Model token üretiyor (kelime parçası, ör. ' fun' + 'ction' + 'al'); başında boşluk olan token yeni kelime başlatıyor.
MLX hesap akışları (stream) thread'e bağlı: model hangi thread'de yüklendiyse orada çalışmalı. Bu yüzden ASR'nin
kendine ait tek bir thread'i var (ThreadPoolExecutor, max_workers=1); yükleme ve bütün çağrılar orada.

Token'ları kelimelere birleştirip her kelimenin başlangıç/bitiş zamanını tutuyoruz.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import mlx.core as mx
import numpy as np
from parakeet_mlx import from_pretrained
from parakeet_mlx.audio import get_logmel

from . import SR

MODEL = "mlx-community/parakeet-tdt-0.6b-v3"


@dataclass
class Word:
    text: str
    start: float  # tur başına göre (sn)
    end: float


@dataclass
class Transcript:
    text: str
    words: list[Word]


def _high_qos() -> None:
    """macOS: bu thread'i "kullanıcı etkileşimli" QoS sınıfına al. Süreç çoğunlukla boştayken macOS thread'leri
    verimlilik (E) çekirdeklerine koyuyor; Parakeet'in Python çözücü döngüsü orada birkaç kat yavaş."""
    try:
        import ctypes
        libc = ctypes.CDLL("/usr/lib/libSystem.dylib")
        QOS_CLASS_USER_INTERACTIVE = 0x21
        libc.pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE, 0)
    except Exception:
        pass


class ASR:
    def __init__(self, model: str = MODEL):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr",
                                       initializer=_high_qos)
        self.model = self.pool.submit(from_pretrained, model).result()
        self._nudge_audio = np.random.default_rng(1).normal(0, 0.05, SR // 2).astype(np.float32)

    def warmup(self) -> None:
        """MLX, GPU çekirdeklerini yeni giriş boylarında ilk kez derliyor; tipik tur boylarını açılışta bir kez geçir.
        Gürültü kullanıyoruz: sıfır ses çözücüyü hemen bitirip yolun bir kısmını hiç çalıştırmıyor."""
        rng = np.random.default_rng(0)
        for sec in (1, 2, 3, 4, 6, 8):
            self.pool.submit(self.transcribe, rng.normal(0, 0.05, sec * SR).astype(np.float32)).result()

    def nudge(self) -> None:
        """GPU'yu uyandır (beklemeden). macOS boşta kalan GPU'yu düşük güce alıyor; tur bitince ilk çağrı 3-5 kat yavaş
        oluyordu (gerçek zamanda ~600-900 ms, beklemesiz ~150 ms). VAD "konuşma başladı" deyince çağrılıyor:
        kişi konuşurken GPU ısınıyor, tur bitince ASR hazır buluyor."""
        if self.pool._work_queue.qsize() == 0:
            self.pool.submit(self.transcribe, self._nudge_audio)

    async def transcribe_async(self, audio: np.ndarray) -> Transcript:
        return await asyncio.get_running_loop().run_in_executor(self.pool, self.transcribe, audio)

    def transcribe(self, audio: np.ndarray) -> Transcript:
        """Sadece ASR thread'inde çağrılmalı (transcribe_async kullan)."""
        mel = get_logmel(mx.array(audio), self.model.preprocessor_config)
        r = self.model.generate(mel)[0]
        words: list[Word] = []
        for s in r.sentences:
            for tk in s.tokens:
                if tk.text.startswith(" ") or not words:
                    words.append(Word(tk.text.strip(), tk.start, tk.end))
                else:  # kelimenin devamı ya da noktalama
                    words[-1].text += tk.text
                    words[-1].end = tk.end
        return Transcript(r.text.strip(), [w for w in words if w.text])

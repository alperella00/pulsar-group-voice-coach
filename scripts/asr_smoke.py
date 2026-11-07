"""ASR smoke testi: parakeet-tdt-0.6b-v3 (MLX) ile AMI'den VAD'ın kestiği gerçek turları yazıya dök.

Ölçülenler: model yükleme süresi, bellek (MLX tepe + süreç RSS), tur başına süre, kelime zaman damgaları.
Kullanım: uv run python scripts/asr_smoke.py [toplantı] [tur_sayısı]
"""
import json
import resource
import sys
import time

import mlx.core as mx
import numpy as np
import soundfile as sf
from parakeet_mlx import from_pretrained
from parakeet_mlx.audio import get_logmel

MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
meeting = sys.argv[1] if len(sys.argv) > 1 else "ES2004a"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6

rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9  # macOS: byte → GB
print(f"başlangıç RSS tepe: {rss():.2f} GB")
t = time.perf_counter()
model = from_pretrained(MODEL)
print(f"model yüklendi: {time.perf_counter() - t:.1f} sn, MLX tepe {mx.get_peak_memory() / 1e9:.2f} GB, RSS tepe {rss():.2f} GB")
print(f"kelime dağarcığı: {len(model.vocabulary)} token, ilk 12: {model.vocabulary[:12]}")

audio, sr = sf.read(f"data/ami/audio/{meeting}.Mix-Headset.wav", dtype="float32")
ev = [json.loads(l) for l in open(f"logs/split/replay_{meeting}.jsonl")]
turns = [e for e in ev if e["event"] == "vad_end" and 2.0 <= e["dur"] <= 8.0][10:10 + n]

times = []
for i, e in enumerate(turns):
    x = audio[int(e["start"] * sr):int(e["t"] * sr)]
    t = time.perf_counter()
    mel = get_logmel(mx.array(x), model.preprocessor_config)
    r = model.generate(mel)[0]
    dt = time.perf_counter() - t
    if i > 0:
        times.append((dt, e["dur"]))  # ilki ısınma (MLX derlemesi), ortalamaya katma
    print(f"\n[{e['start']:.2f} – {e['t']:.2f}] {e['dur']:.1f} sn  → {dt * 1000:.0f} ms")
    print(f"  metin: {r.text.strip()}")
    toks = [tk for s in r.sentences for tk in s.tokens]
    print("  token'lar (ilk 12): " + " ".join(f"[{tk.text!r} {tk.start:.2f}-{tk.end:.2f}]" for tk in toks[:12]))

ms = [d * 1000 for d, _ in times]
rt = [dur / d for d, dur in times]
print(f"\nısınma sonrası: tur başına medyan {np.median(ms):.0f} ms, gerçek zamanın medyan {np.median(rt):.0f} katı")
print(f"MLX tepe bellek {mx.get_peak_memory() / 1e9:.2f} GB, süreç RSS tepe {rss():.2f} GB")

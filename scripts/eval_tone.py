"""M6: COACH NOTE'taki ton talimatı Pulsar'ın konuşmasını gerçekten değiştiriyor mu?

Aynı kullanıcı turu (pros_slow) Gemini'ye N kez normal notla, N kez "struggling" notuyla gönderiliyor (her deneme
ayrı oturum). Pulsar'ın sesli cevabı kendi ASR'mizle yazıya dökülüp aynı prosodi koduyla ölçülüyor:
konuşma hızı (hece/sn), kelime sayısı, cümle başına kelime, duraksama.
Kullanım: uv run python scripts/eval_tone.py [N]
"""
import asyncio
import json
import sys
import time

import numpy as np
import soundfile as sf
import soxr

sys.path.insert(0, "src")
from pulsar.asr import ASR  # noqa: E402
from pulsar.coach import SYSTEM, Coach  # noqa: E402
from pulsar.prosody import measure  # noqa: E402
from pulsar.s2s import GeminiLive  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3


async def one(x, note):
    chunks, done = [], asyncio.Event()
    res = {}

    async def on_done(text):
        res["text"] = text
        done.set()

    def on_event(kind, **kw):
        if kind == "first_audio":
            res["ttfb_ms"] = kw["ttfb_ms"]

    async with GeminiLive(SYSTEM, chunks.append, on_done, on_event) as g:
        await g.send_turn(x, note)
        await asyncio.wait_for(done.wait(), 30)
    res["audio"] = b"".join(chunks)
    return res


async def main():
    asr = ASR()
    asr.warmup()
    x, _ = sf.read("data/user/pros_slow.wav", dtype="float32")
    rows = []
    for state in ("normal", "struggling"):
        for i in range(N):
            note = Coach().note("Alper", state)
            try:
                r = await one(x, note)
            except (TimeoutError, asyncio.TimeoutError):
                row = dict(state=state, trial=i, silent=True)
                rows.append(row)
                print(json.dumps(row), flush=True)
                continue
            y = np.frombuffer(r["audio"], np.int16).astype(np.float32) / 32768
            y16 = soxr.resample(y, 24000, 16000).astype(np.float32)
            tr = asr.pool.submit(asr.transcribe, y16).result()
            f = measure(tr.words, y16)
            sents = max(1, sum(r["text"].count(c) for c in ".?!"))
            row = dict(state=state, trial=i, ttfb_ms=r.get("ttfb_ms"), audio_s=round(len(y) / 24000, 2),
                       words=len(tr.words), words_per_sent=round(len(tr.words) / sents, 1),
                       rate=round(f.rate, 2) if f else None, pauses=f.pauses if f else None,
                       pause_ms=round(f.pause_ms) if f else None, reply=r["text"])
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            sf.write(f"logs/replies/tone_{state}_{i}.wav", y, 24000)
            time.sleep(1)
    with open("reports/tone_test.jsonl", "w") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("\n| Not | n | Hız (hece/sn) | Süre (sn) | Kelime | Kelime/cümle | Duraksama |")
    print("|---|---|---|---|---|---|---|")
    for st in ("normal", "struggling"):
        s = [r for r in rows if r["state"] == st and not r.get("silent")]
        silent = sum(1 for r in rows if r["state"] == st and r.get("silent"))
        print(f"| ({st}: {silent} deneme sessiz kaldı) |")
        m = lambda k: np.mean([r[k] for r in s if r[k] is not None])  # noqa: E731
        print(f"| {st} | {len(s)} | {m('rate'):.2f} | {m('audio_s'):.1f} | {m('words'):.1f} | {m('words_per_sent'):.1f} | {m('pauses'):.1f} |")


if __name__ == "__main__":
    asyncio.run(main())

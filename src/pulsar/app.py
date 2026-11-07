"""Görevleri birbirine bağlayan ana döngü (MIMARI §4 "Süreç yapısı").

  replay ──blok kuyruğu──► vad_task ──tur kuyruğu──► turn_worker
     (32 ms bloklar)        (Silero, tur kesme)        (ses parmak izi; ağır iş ayrı thread'de)
                     herkes ──► EventLog (JSONL)

turn_worker turu gerekirse alt turlara böler (segment.py, K20).
Sırada: turn_worker'a ASR + hitap kuralları, ardından Gemini istemcisi eklenecek.
"""
import argparse
import asyncio
import time

from . import SR
from .audio_in import load_wav, replay
from .events import EventLog
from .rttm import enrollment_spans, load_rttm
from .segment import split_turn
from .speaker import SpeakerID
from .vad import TurnSegmenter


def enroll_from_rttm(spk: SpeakerID, audio, rttm_path: str, log: EventLog) -> None:
    segs = load_rttm(rttm_path)
    for name, spans in enrollment_spans(segs, len(audio) / SR).items():
        import numpy as np
        x = np.concatenate([audio[int(a * SR):int(b * SR)] for a, b in spans])
        n = spk.enroll(name, x)
        log.write("enroll", name=name, seconds=round(len(x) / SR, 1), windows=n, spans=spans)
        print(f"kayıt  {name:<10} {len(x) / SR:5.1f} sn, {len(spans)} parça, {n} pencere")


async def run(args) -> None:
    log = EventLog(args.log)
    full = load_wav(args.wav)
    spk = SpeakerID(tau=args.tau, margin=args.margin)
    enroll_from_rttm(spk, full, args.rttm, log)

    audio = full[int(args.start * SR):] if args.max_s is None else \
        full[int(args.start * SR):int((args.start + args.max_s) * SR)]
    seg = TurnSegmenter(threshold=args.vad_th, min_silence_ms=args.min_silence_ms)
    blocks: asyncio.Queue = asyncio.Queue(maxsize=256)
    turns: asyncio.Queue = asyncio.Queue()
    log.write("replay_start", t=args.start, wav=args.wav, speed=args.speed, tau=args.tau, margin=args.margin,
              vad_th=args.vad_th, min_silence_ms=args.min_silence_ms)

    async def vad_task():
        while (item := await blocks.get()) is not None:
            t, block = item
            for kind, val in seg.push(t, block, time.monotonic()):
                if kind == "start":
                    log.write("vad_start", t=val)
                else:
                    log.write("vad_end", t=val.end, turn=val.id, start=val.start, dur=round(val.dur, 3),
                              detect_lag_ms=round((time.monotonic() - val.end_wall) * 1000, 1))
                    await turns.put(val)
        for _, val in seg.flush():
            log.write("vad_end", t=val.end, turn=val.id, start=val.start, dur=round(val.dur, 3))
            await turns.put(val)
        await turns.put(None)

    async def turn_worker():
        while (turn := await turns.get()) is not None:
            t0 = time.perf_counter()
            if args.split:
                # kimliğe bakarak turu alt turlara böl (segment.py); ağır iş ayrı thread'de, VAD bu sırada çalışıyor
                pieces, info = await asyncio.to_thread(split_turn, spk, turn.audio, turn.probs, seg.neg_th)
            else:
                pieces, info = [None], {}
            ms = (time.perf_counter() - t0) * 1000
            if len(pieces) > 1:
                log.write("split", t=turn.end, turn=turn.id, **info, split_ms=round(ms, 1))
            for k, pc in enumerate(pieces):
                if pc is None:  # bölme kapalı: eski davranış, turun tamamı
                    r = await asyncio.to_thread(spk.identify, turn.audio)
                    a, b = turn.start, turn.end
                else:
                    r, a, b = pc.result, turn.start + pc.start, turn.start + pc.end
                fields = dict(turn=turn.id, sub=k, start=round(a, 3), end=round(b, 3))
                if r is None:
                    log.write("speaker", t=b, **fields, name=None, reason="short")
                    who, extra = "— (kısa, isim yok)", ""
                else:
                    log.write("speaker", t=b, **fields, name=r.name, best_name=r.best_name, best=r.best,
                              margin=r.margin, scores=r.scores)
                    who, extra = r.name or f"unknown (~{r.best_name})", f"skor {r.best:.2f}  fark {r.margin:.2f}"
                tag = f" ↳{k}" if len(pieces) > 1 else "   "
                print(f"[{a:7.2f} – {b:7.2f}]{tag} {b - a:4.1f} sn  {who:<22} {extra}")
            log.write("turn_done", t=turn.end, turn=turn.id, pieces=len(pieces), work_ms=round(ms, 1))

    t_start = time.monotonic()
    await asyncio.gather(replay(audio, blocks, start_s=args.start, speed=args.speed), vad_task(), turn_worker())
    log.write("replay_end", elapsed_s=round(time.monotonic() - t_start, 1))
    log.close()
    print(f"\nbitti: {len(audio) / SR:.0f} sn ses, {time.monotonic() - t_start:.1f} sn sürdü → {args.log}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="pulsar", description="Pulsar replay: WAV → VAD → tur → ses parmak izi")
    ap.add_argument("--meeting", default="ES2004a", help="AMI toplantı kodu (wav/rttm yolları bundan türer)")
    ap.add_argument("--wav")
    ap.add_argument("--rttm")
    ap.add_argument("--start", type=float, default=0.0, help="replay'e kaçıncı saniyeden başlansın")
    ap.add_argument("--max-s", dest="max_s", type=float, default=None, help="en fazla kaç saniye")
    ap.add_argument("--speed", type=float, default=1.0, help="1=gerçek zaman, 0=beklemeden (ölçüm)")
    ap.add_argument("--tau", type=float, default=0.45)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--vad-th", dest="vad_th", type=float, default=0.5)
    ap.add_argument("--min-silence-ms", dest="min_silence_ms", type=int, default=500)
    ap.add_argument("--no-split", dest="split", action="store_false", help="turu bölme (eski davranış)")
    ap.add_argument("--log")
    args = ap.parse_args()
    args.wav = args.wav or f"data/ami/audio/{args.meeting}.Mix-Headset.wav"
    args.rttm = args.rttm or f"data/ami/rttm/{args.meeting}.rttm"
    args.log = args.log or f"logs/replay_{args.meeting}.jsonl"
    asyncio.run(run(args))

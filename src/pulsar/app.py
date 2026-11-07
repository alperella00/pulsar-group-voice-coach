"""Görevleri birbirine bağlayan ana döngü (MIMARI §4 "Süreç yapısı").

  replay ──blok kuyruğu──► vad_task ──tur kuyruğu──► turn_worker ──hitap EVET──► Gemini Live ──► Player
     (32 ms bloklar)        (Silero, tur kesme)        · konuşmacı bölme (segment.py, K20)   (s2s.py)     (24 kHz)
                                                       · ASR (asr.py), paralel
                                                       · hitap kuralları (addressing.py, K21)
                     herkes ──► EventLog (JSONL)

Tur yöneticisi (MIMARI §5.8, sadeleştirilmiş):
  IDLE ──hitap──► WAITING ──ilk ses──► PULSAR_SPEAKING ──cevap bitti──► IDLE + takip penceresi (addressing.on_reply)
                    └──10 sn ses yok──► IDLE (model_silent)
  Pulsar konuşurken isimle hitap → söz kesme (oynatma kesilir, yeni tur gönderilir); diğer durumlarda atlanır.

Konuşma sayacı (MIMARI §5.10): tanınan her alt turun süresi o kişiye yazılır (unknown/kısa sayılmaz).
Proaktif soru (MIMARI §5.11): ≥ 3 sn sessizlik + birinin payı < %15 (ilk 2 dk'dan sonra) + son proaktiften ≥ 60 sn
→ o kişiye, son konuşmalarla ilgili kısa bir soru (sadece metin talimatı).
"""
import argparse
import asyncio
import time
from collections import defaultdict

import numpy as np

from . import SR
from .addressing import Addressing
from .asr import ASR
from .audio_in import load_wav, replay
from .coach import SYSTEM, Coach
from .events import EventLog
from .prosody import Baseline, measure
from .asr import Word
from .rttm import enrollment_spans, load_rttm
from .segment import split_turn
from .speaker import SpeakerID
from .vad import TurnSegmenter

SILENT_TIMEOUT_S = 10.0
PRO_SILENCE_S, PRO_SHARE, PRO_AFTER_S, PRO_GAP_S = 3.0, 0.15, 120.0, 60.0


async def timed(coro):
    t0 = time.perf_counter()
    r = await coro
    return r, (time.perf_counter() - t0) * 1000


def enroll_from_rttm(spk: SpeakerID, audio, rttm_path: str, log: EventLog) -> dict[str, np.ndarray]:
    segs = load_rttm(rttm_path)
    out = {}
    for name, spans in enrollment_spans(segs, len(audio) / SR).items():
        x = np.concatenate([audio[int(a * SR):int(b * SR)] for a, b in spans])
        n = spk.enroll(name, x)
        out[name] = x
        log.write("enroll", name=name, seconds=round(len(x) / SR, 1), windows=n, spans=spans)
        print(f"kayıt  {name:<10} {len(x) / SR:5.1f} sn, {len(spans)} parça, {n} pencere")
    return out


async def run(args) -> None:
    log = EventLog(args.log)
    full = load_wav(args.wav)
    spk = SpeakerID(tau=args.tau, margin=args.margin)
    enroll_audio = enroll_from_rttm(spk, full, args.rttm, log)
    asr = None
    if args.asr:
        t0 = time.perf_counter()
        if not args.qos:
            import pulsar.asr as _a
            _a._high_qos = lambda: None
        asr = ASR()
        asr.warmup()  # ilk çağrıdaki ~2 sn'lik MLX derlemesini açılışta öde
        print(f"ASR hazır: {time.perf_counter() - t0:.1f} sn")
    # prosodi normali: kişinin kayıt sesinden (tanıtım) hız, MLR, duraksama, pitch ortalaması ve sapması
    baselines = {}
    if asr:
        for name, x in enroll_audio.items():
            b = Baseline(asr.pool.submit(asr.transcribe, x).result().words, x)
            baselines[name] = b
            log.write("prosody_baseline", name=name, parts=b.n, **{k: [round(m, 2), round(sd, 2)] for k, (m, sd) in b.stats.items()})
            print(f"normal {name:<10} " + ", ".join(f"{k} {m:.1f}±{sd:.1f}" for k, (m, sd) in b.stats.items()))

    audio = full[int(args.start * SR):] if args.max_s is None else \
        full[int(args.start * SR):int((args.start + args.max_s) * SR)]
    seg = TurnSegmenter(threshold=args.vad_th, min_silence_ms=args.min_silence_ms)
    blocks: asyncio.Queue = asyncio.Queue(maxsize=256)
    turns: asyncio.Queue = asyncio.Queue()
    clock = {"t": args.start}  # replay'in şu anki medya zamanı (sn)
    log.write("replay_start", t=args.start, wav=args.wav, speed=args.speed, tau=args.tau, margin=args.margin,
              vad_th=args.vad_th, min_silence_ms=args.min_silence_ms, gemini=args.gemini)

    # --- hitap + Gemini + tur yöneticisi ---
    addr = Addressing(spk.names)
    coach = Coach()
    state = {"name": "IDLE", "to": None, "n": 0}
    talk = defaultdict(float)  # kişi → konuşma süresi (sn)
    for nm in spk.names:
        talk[nm] = 0.0
    quiet = {"last_speech": args.start, "last_pro": -1e9, "done": False}

    def shares() -> dict[str, float]:
        tot = sum(talk.values())
        return {k: v / tot for k, v in talk.items()} if tot > 0 else {}

    def talk_bar() -> str:
        return "  ".join(f"{k} {'█' * round(v * 20):<20} %{v * 100:4.1f}" for k, v in shares().items())
    gem = player = None

    if args.gemini:
        from .player import Player
        from .s2s import GeminiLive
        player = Player(play=args.play, save_dir="logs/replies")

        def on_event(kind, **kw):
            log.write(kind, t=clock["t"], **kw)
            if kind == "first_audio":
                state["name"] = "PULSAR_SPEAKING"
                print(f"{'':28}⟵ Pulsar ilk ses: {kw['ttfb_ms']:.0f} ms")

        async def on_done(text: str):
            n = state["n"]
            dur = player.finish_reply()
            if dur == 0 and not text:  # söz kesmeden sonra eski üretim için gelen boş "bitti": durumu değiştirme
                log.write("empty_done", t=clock["t"])
                return
            wait = max(player.end_wall - time.monotonic(), 0.0)
            await asyncio.sleep(wait)  # ses çalınıp bitene kadar bekle (takip penceresi cevabın sonundan başlar)
            if state["n"] != n:  # bu sırada söz kesildi, yeni tur gönderildi: eski cevap pencere açmasın
                return
            quiet["last_speech"] = clock["t"]  # Pulsar'ın konuşması da sessizlik değil
            asked = text.rstrip().endswith("?")
            addr.on_reply(state["to"], clock["t"], asked)
            log.write("response_done", t=clock["t"], audio_s=round(dur, 2), asked=asked)
            print(f"{'':28}⟵ Pulsar ({dur:.1f} sn): “{text}”")
            state["name"] = "IDLE"

        gem = GeminiLive(SYSTEM, player.write, on_done, on_event)
        await gem.__aenter__()
        print("Gemini Live bağlandı")

    async def watchdog(n: int):
        await asyncio.sleep(SILENT_TIMEOUT_S)
        if state["n"] == n and state["name"] == "WAITING":
            log.write("model_silent", t=clock["t"])
            print(f"{'':28}⟵ Pulsar sessiz kaldı ({SILENT_TIMEOUT_S:.0f} sn)")
            state["name"] = "IDLE"

    async def handle_piece(name, text, x, a, b, turn_id, state_p=None):
        if asr is None or not text:
            return
        d = addr.decide(text, name, a)
        if not d.addressed:
            coach.heard(name, text)
            if d.rule == "other_person":
                log.write("not_addressed", t=b, turn=turn_id, rule=d.rule)
            return
        log.write("addressed", t=b, turn=turn_id, rule=d.rule, speaker=name)
        print(f"{'':28}→ Pulsar'a hitap [{d.rule}{': ' + d.detail if d.detail else ''}]")
        if gem is None:
            return
        if state["name"] != "IDLE":
            # söz kesme sadece Pulsar gerçekten konuşurken: WAITING'de (henüz ses yok) Gemini "interrupted"
            # göndermiyor ve yeni cevabın parçaları eski cevabınki sanılıp atılıyordu (ölçümde böyle oldu)
            if d.rule != "name" or not args.barge_in or state["name"] != "PULSAR_SPEAKING":
                log.write("busy_skip", t=b, turn=turn_id, state=state["name"])
                print(f"{'':28}  (Pulsar meşgul: {state['name']}, atlandı)")
                return
            # söz kesme: Pulsar konuşurken biri ona ismiyle sesleniyor → sustur, yeni soruya geç
            log.write("barge_in", t=b, turn=turn_id, state=state["name"])
            print(f"{'':28}  ✋ söz kesme: Pulsar susuyor ({state['name']})")
            player.clear()
            player.finish_reply()
            gem.interrupt()
        state.update(name="WAITING", to=name, n=state["n"] + 1)
        note = coach.note(name, state_p)
        t0 = time.perf_counter()
        await gem.send_turn(x, note)
        log.write("activity_end", t=clock["t"], turn=turn_id, send_ms=round((time.perf_counter() - t0) * 1000, 1),
                  lag_since_turn_end_s=round(clock["t"] - b, 2))
        asyncio.create_task(watchdog(state["n"]))

    async def vad_task():
        while (item := await blocks.get()) is not None:
            t, block = item
            clock["t"] = t
            for kind, val in seg.push(t, block, time.monotonic()):
                if kind == "start":
                    log.write("vad_start", t=val)
                    if asr and args.nudge:
                        asr.nudge()
                else:
                    log.write("vad_end", t=val.end, turn=val.id, start=val.start, dur=round(val.dur, 3),
                              detect_lag_ms=round((time.monotonic() - val.end_wall) * 1000, 1))
                    quiet["last_speech"] = val.end
                    await turns.put(val)
        for _, val in seg.flush():
            log.write("vad_end", t=val.end, turn=val.id, start=val.start, dur=round(val.dur, 3))
            await turns.put(val)
        await turns.put(None)

    worker = {"busy": False}

    async def turn_worker():
        while (turn := await turns.get()) is not None:
            worker["busy"] = True
            t0 = time.perf_counter()
            # konuşmacı bölme ve ASR aynı anda, ayrı thread'lerde; VAD bu sırada çalışmaya devam ediyor
            jobs = [asyncio.to_thread(split_turn, spk, turn.audio, turn.probs, seg.neg_th) if args.split
                    else asyncio.sleep(0, ([None], {}))]
            if asr:
                jobs.append(timed(asr.transcribe_async(turn.audio)))
            out = await asyncio.gather(*jobs)
            pieces, info = out[0]
            tr, asr_ms = out[1] if asr else (None, 0.0)
            ms = (time.perf_counter() - t0) * 1000
            if tr is not None:
                log.write("asr", t=turn.end, turn=turn.id, n_words=len(tr.words), asr_ms=round(asr_ms, 1))
            if len(pieces) > 1:
                log.write("split", t=turn.end, turn=turn.id, **info, split_ms=round(ms, 1))
            for k, pc in enumerate(pieces):
                if pc is None:  # bölme kapalı: eski davranış, turun tamamı
                    r = await asyncio.to_thread(spk.identify, turn.audio)
                    a, b = turn.start, turn.end
                else:
                    r, a, b = pc.result, turn.start + pc.start, turn.start + pc.end
                fields = dict(turn=turn.id, sub=k, start=round(a, 3), end=round(b, 3))
                if r is not None and r.name:
                    talk[r.name] += b - a
                if r is None:
                    log.write("speaker", t=b, **fields, name=None, reason="short")
                    who, extra = "— (kısa, isim yok)", ""
                else:
                    log.write("speaker", t=b, **fields, name=r.name, best_name=r.best_name, best=r.best,
                              margin=r.margin, scores=r.scores)
                    who, extra = r.name or f"unknown (~{r.best_name})", f"skor {r.best:.2f}  fark {r.margin:.2f}"
                tag = f" ↳{k}" if len(pieces) > 1 else "   "
                print(f"[{a:7.2f} – {b:7.2f}]{tag} {b - a:4.1f} sn  {who:<22} {extra}")
                text, pw = "", []
                if tr is not None:  # kelimeyi, orta noktası bu alt turun içine düşüyorsa bu alt tura yaz
                    lo, hi = a - turn.start, b - turn.start
                    pw = [Word(w.text, w.start - lo, w.end - lo) for w in tr.words if lo <= (w.start + w.end) / 2 < hi]
                    text = " ".join(w.text for w in pw)
                    if text:
                        print(f"{'':28}“{text}”")
                x = turn.audio[int((a - turn.start) * SR):int((b - turn.start) * SR)]
                state_p = None
                if r and r.name in baselines and (f := measure(pw, x)):
                    f = baselines[r.name].assess(f)
                    state_p = f.state
                    log.write("prosody", t=b, turn=turn.id, sub=k, speaker=r.name, rate=round(f.rate, 2),
                              pauses=f.pauses, pause_ms=round(f.pause_ms), mlr=round(f.mlr, 1), fillers=f.fillers,
                              f0=round(f.f0, 1) if f.f0 else None, z=f.z, state=f.state, signals=f.signals)
                    if f.state != "normal":
                        print(f"{'':28}~ prosodi: {f.state} {f.signals} (hız z {f.z.get('rate', 0):+.1f})")
                await handle_piece(r.name if r else None, text, x, a, b, turn.id, state_p)
            log.write("turn_done", t=turn.end, turn=turn.id, pieces=len(pieces), work_ms=round(ms, 1))
            if args.talk_bar and shares():
                print(f"{'':28}▌ {talk_bar()}")
            worker["busy"] = False

    async def proactive_monitor():
        while not quiet["done"]:
            await asyncio.sleep(0.25)
            # işlenmeyi bekleyen tur varken karar verme: sayaç geride kalmış olabilir (ölçümde böyle oldu)
            if gem is None or state["name"] != "IDLE" or seg.in_speech or turns.qsize() or worker["busy"]:
                continue
            now = clock["t"]
            sh = shares()
            if (now - quiet["last_speech"] < PRO_SILENCE_S or now - args.start < PRO_AFTER_S
                    or now - quiet["last_pro"] < PRO_GAP_S or not sh):
                continue
            target, share = min(sh.items(), key=lambda kv: kv[1])
            if share >= PRO_SHARE:
                continue
            quiet["last_pro"] = now
            state.update(name="WAITING", to=target, n=state["n"] + 1)
            log.write("proactive", t=now, target=target, share=round(share, 3),
                      silence_s=round(now - quiet["last_speech"], 2))
            print(f"[{now:7.2f}]  ⚑ proaktif: {target} az konuşuyor (%{share * 100:.1f}), "
                  f"{now - quiet['last_speech']:.1f} sn sessizlik → soru")
            await gem.send_text(coach.proactive(target))
            asyncio.create_task(watchdog(state["n"]))

    async def pipeline():
        await asyncio.gather(replay(audio, blocks, start_s=args.start, speed=args.speed), vad_task(), turn_worker())
        quiet["done"] = True

    t_start = time.monotonic()
    try:
        await asyncio.gather(pipeline(), proactive_monitor())
        if gem:  # son cevabın bitmesini bekle
            for _ in range(int(SILENT_TIMEOUT_S * 10)):
                if state["name"] == "IDLE":
                    break
                await asyncio.sleep(0.1)
    finally:
        if gem:
            await gem.__aexit__(None, None, None)
    log.write("replay_end", elapsed_s=round(time.monotonic() - t_start, 1), talk_s={k: round(v, 1) for k, v in talk.items()})
    if shares():
        print(f"\nkonuşma payı: {talk_bar()}")
    log.close()
    print(f"\nbitti: {len(audio) / SR:.0f} sn ses, {time.monotonic() - t_start:.1f} sn sürdü → {args.log}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="pulsar", description="Pulsar replay: WAV → VAD → tur → kim/ne → hitap → Gemini")
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
    ap.add_argument("--no-asr", dest="asr", action="store_false", help="ASR'yi kapat")
    ap.add_argument("--no-nudge", dest="nudge", action="store_false", help="konuşma başlarken GPU'yu ısıtma")
    ap.add_argument("--no-qos", dest="qos", action="store_false", help="(deney) ASR thread'ini yüksek önceliğe alma")
    ap.add_argument("--gemini", action="store_true", help="hitap edilen turları Gemini Live'a gönder (speed 1 olmalı)")
    ap.add_argument("--play", action="store_true", help="Pulsar'ın sesini hoparlörden çal")
    ap.add_argument("--no-barge-in", dest="barge_in", action="store_false", help="isimle hitapta Pulsar'ı susturma")
    ap.add_argument("--no-talk-bar", dest="talk_bar", action="store_false", help="her turdan sonra konuşma payını basma")
    ap.add_argument("--log")
    args = ap.parse_args()
    if args.gemini and args.speed != 1:
        ap.error("--gemini gerçek zaman ister (--speed 1)")
    args.wav = args.wav or f"data/ami/audio/{args.meeting}.Mix-Headset.wav"
    args.rttm = args.rttm or f"data/ami/rttm/{args.meeting}.rttm"
    args.log = args.log or f"logs/replay_{args.meeting}.jsonl"
    asyncio.run(run(args))

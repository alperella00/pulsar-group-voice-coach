"""Replay günlüğünü (logs/replay_*.jsonl) RTTM ile karşılaştırır.

Her VAD turu için:
  - RTTM'ye göre turun içinde kim ne kadar konuşmuş → en çok konuşan = turun sahibi
  - saflık = sahibin süresi / turdaki toplam konuşma süresi (1,0 = tek kişilik tur)
  - RTTM'de hiç konuşma yoksa → VAD'ın yanlış alarmı
  - turun yarısından fazlası kayıt aralığındaysa → sayılmıyor (kayıtta kullanılan sesi test etmeyelim)
Sonuç: doğru / unknown / yanlış isim; tek kişilik turlar ve karışık turlar ayrı.

Kullanım: uv run python scripts/eval_replay.py [--dir logs/xyz] ES2004a IS1009a ...
"""
import json
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, "src")
from pulsar.rttm import load_rttm  # noqa: E402

PURE = 0.8  # bu saflığın üstü "tek kişilik tur" sayılıyor


def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))


LOGDIR = "logs"


def evaluate(meeting: str) -> dict:
    ev = [json.loads(l) for l in open(f"{LOGDIR}/replay_{meeting}.jsonl")]
    segs = load_rttm(f"data/ami/rttm/{meeting}.rttm")
    enroll = [tuple(s) for e in ev if e["event"] == "enroll" for s in e["spans"]]
    turns = {e["turn"]: e for e in ev if e["event"] == "vad_end"}
    rows = []
    for e in (e for e in ev if e["event"] == "speaker"):
        tv = turns[e["turn"]]
        s, t = e.get("start", tv["start"]), e.get("end", tv["t"])   # bölünmüş turlarda alt turun sınırları
        if sum(overlap(s, t, a, b) for a, b in enroll) > 0.5 * (t - s):
            continue
        per = Counter()
        for a, b, spk in segs:
            per[spk] += overlap(s, t, a, b)
        tot = sum(per.values())
        if tot < 0.05:
            rows.append(dict(kind="false_alarm", dur=t - s))
            continue
        owner, own_s = per.most_common(1)[0]
        pure = own_s / tot
        res = "unknown" if e["name"] is None else ("correct" if e["name"] == owner else "wrong")
        # konuşma süresine göre: isim verilen kişinin RTTM'deki süresi doğru, diğerlerininki yanlış
        if e["name"] is None:
            secs = dict(correct=0.0, wrong=0.0, unknown=tot)
        else:
            secs = dict(correct=per[e["name"]], wrong=tot - per[e["name"]], unknown=0.0)
        rows.append(dict(kind=res, dur=t - s, pure=pure, short=e.get("reason") == "short", secs=secs))
    return dict(meeting=meeting, rows=rows,
                lags=[t["detect_lag_ms"] for t in turns.values() if "detect_lag_ms" in t])


def pct(n, d):
    return f"%{100 * n / d:.1f}" if d else "-"


def main():
    global LOGDIR
    args = sys.argv[1:]
    if args[:1] == ["--dir"]:
        LOGDIR, args = args[1], args[2:]
    meetings = args or ["ES2004a"]
    allrows = []
    print(f"| Toplantı | Tur | Medyan süre | Yanlış alarm | Tek kişilik (saflık ≥ {PURE}) | Doğru | Unknown | Yanlış isim |")
    print("|---|---|---|---|---|---|---|---|")
    for m in meetings:
        r = evaluate(m)
        rows = r["rows"]
        allrows += rows
        sp = [x for x in rows if x["kind"] != "false_alarm"]
        c = Counter(x["kind"] for x in sp)
        fa = sum(x["kind"] == "false_alarm" for x in rows)
        print(f"| {m} | {len(rows)} | {np.median([x['dur'] for x in rows]):.1f} sn | {pct(fa, len(rows))} | "
              f"{pct(sum(x['pure'] >= PURE for x in sp), len(sp))} | {pct(c['correct'], len(sp))} | "
              f"{pct(c['unknown'], len(sp))} | {pct(c['wrong'], len(sp))} |")
    sp = [x for x in allrows if x["kind"] != "false_alarm"]
    print("\nToplam, saflığa göre:")
    for nm, sub in [("tek kişilik turlar", [x for x in sp if x["pure"] >= PURE]),
                    ("karışık turlar", [x for x in sp if x["pure"] < PURE]),
                    ("hepsi", sp)]:
        c = Counter(x["kind"] for x in sub)
        print(f"  {nm:<20} n={len(sub):4d}  doğru {pct(c['correct'], len(sub))}  unknown {pct(c['unknown'], len(sub))}"
              f"  yanlış isim {pct(c['wrong'], len(sub))}")
    for nm, lo, hi in [("< 1 sn", 0, 1), ("1-2 sn", 1, 2), ("2-4 sn", 2, 4), ("≥ 4 sn", 4, 1e9)]:
        sub = [x for x in sp if lo <= x["dur"] < hi]
        c = Counter(x["kind"] for x in sub)
        print(f"  süre {nm:<8} n={len(sub):4d}  doğru {pct(c['correct'], len(sub))}  unknown {pct(c['unknown'], len(sub))}"
              f"  yanlış isim {pct(c['wrong'], len(sub))}")
    T = {k: sum(x["secs"][k] for x in sp) for k in ("correct", "unknown", "wrong")}
    tt = sum(T.values())
    print(f"\nKonuşma süresine göre ({tt / 60:.0f} dk): doğru kişiye {pct(T['correct'], tt)}, isimsiz {pct(T['unknown'], tt)},"
          f" yanlış kişiye {pct(T['wrong'], tt)}")
    print(f"Kısa olduğu için isim verilmeyen: {sum(x['short'] for x in sp)} birim")


if __name__ == "__main__":
    main()

"""Ses parmak izi: AMI gerçek toplantı testi (MIMARI §7, M1/M2/M3).

LibriSpeech temiz sesli kitap kaydıydı. Burada 4 kişinin gerçekten birbiriyle konuştuğu toplantılar var
(Mix-Headset: herkesin yaka mikrofonunun toplamı = online görüşmedeki karışık akışa en yakın kayıt).

Adımlar (her toplantı için):
  1. RTTM'den "temiz" aralıklar: sadece bir kişinin konuştuğu anlar (örtüşmeler çıkarılır).
  2. Kayıt: her kişinin kronolojik ilk temiz konuşması, min(25 sn, temiz konuşmasının yarısı) kadar.
     2 sn'lik %50 örtüşen parçalar → embedding → ortalama merkez vektör (LibriSpeech'tekiyle aynı).
  3. Test: kayıtta kullanılmayan temiz aralıklar.
       - sabit uzunluk: >= L sn olan aralığın başından L sn (L = 1, 2, 4)
       - doğal tur: aralığın tamamı (>= 1 sn, en fazla 8 sn) → gerçek tur uzunluklarıyla doğruluk
  4. Senaryolar:
       - 4 kişi kayıtlı (N=4)
       - 3 kişi kayıtlı + 1 kayıtsız (4 farklı kişi dışarıda bırakılarak) → kayıtsız kişi kabul oranı
  5. Konuşma payı (M3): RTTM'de konuşma olan her 1,5 sn'lik pencere en yakın profile atanır
     (VAD yerine RTTM kullanılıyor = mükemmel VAD varsayımı). Tahmini paylar gerçek paylarla karşılaştırılır.

Kullanım: uv run python scripts/speaker_id_ami.py
Çıktı: reports/speaker_id_ami.md ve .json
"""
import itertools
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf

MEETINGS = ["ES2004a", "IS1009a", "TS3003a", "EN2002a"]
MODEL = "models/wespeaker_en_voxceleb_resnet34_LM.onnx"
SR = 16000
ENROLL_MAX_S = 25.0
CHUNK_S, HOP_S = 2.0, 1.0
TEST_LENS = (1.0, 2.0, 4.0)
NATURAL_MIN, NATURAL_MAX = 1.0, 8.0
MAX_TESTS = 80  # kişi ve uzunluk başına üst sınır (çok konuşan kişi sonucu domine etmesin)
WIN_S = 1.5
SETTINGS = {"başlangıç": (0.50, 0.10), "LibriSpeech ızgarası": (0.30, 0.05)}
GRID_TAU = np.round(np.arange(0.20, 0.71, 0.05), 2)
GRID_M = np.round(np.arange(0.00, 0.31, 0.05), 2)

ext = sherpa_onnx.SpeakerEmbeddingExtractor(
    sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=MODEL, num_threads=4))


def embed(x):
    s = ext.create_stream()
    s.accept_waveform(SR, x)
    s.input_finished()
    v = np.asarray(ext.compute(s), dtype=np.float32)
    return v / np.linalg.norm(v)


def load_meeting(m):
    audio, sr = sf.read(f"data/ami/audio/{m}.Mix-Headset.wav", dtype="float32")
    assert sr == SR
    segs = []
    for line in Path(f"data/ami/rttm/{m}.rttm").read_text().splitlines():
        p = line.split()
        segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    # 10 ms çözünürlükte zaman çizelgesi: her dilimde kim konuşuyor
    T = int(len(audio) / SR * 100) + 1
    count = np.zeros(T, np.int16)
    owner = defaultdict(lambda: np.zeros(T, bool))
    for s, e, spk in segs:
        a, b = int(s * 100), min(int(e * 100), T)
        count[a:b] += 1
        owner[spk][a:b] = True
    return audio, dict(owner), count


def runs(mask):
    """Boolean maskedeki ardışık True aralıkları (sn cinsinden)."""
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return [(a / 100, b / 100) for a, b in zip(starts, ends)]


def build(m):
    audio, owner, count = load_meeting(m)
    cut = lambda a, b: audio[int(a * SR): int(b * SR)]  # noqa: E731
    spk = {}
    for s, own in owner.items():
        clean = runs(own & (count == 1))
        clean_total = sum(b - a for a, b in clean)
        target = min(ENROLL_MAX_S, clean_total / 2)
        enroll, used, acc = [], 0, 0.0
        for a, b in clean:  # kronolojik ilk temiz konuşma
            take = min(b - a, target - acc)
            enroll.append(cut(a, a + take))
            acc += take
            used += 1
            if acc >= target - 1e-6:
                break
        x = np.concatenate(enroll)
        size, step = int(CHUNK_S * SR), int(HOP_S * SR)
        if len(x) < size:
            x = np.pad(x, (0, size - len(x)))
        ch = np.stack([embed(x[i:i + size]) for i in range(0, len(x) - size + 1, step)])
        c = ch.mean(0)
        c /= np.linalg.norm(c)
        rest = clean[used:]  # kayıtta kullanılmayan aralıklar
        tests = {}
        for L in TEST_LENS:
            tests[L] = [embed(cut(a, a + L)) for a, b in rest if b - a >= L][:MAX_TESTS]
        nat = [(a, b) for a, b in rest if b - a >= NATURAL_MIN][:MAX_TESTS]
        tests["natural"] = [embed(cut(a, min(b, a + NATURAL_MAX))) for a, b in nat]
        nat_len = [min(b - a, NATURAL_MAX) for a, b in nat]
        spk[s] = {"centroid": c, "enroll_s": round(acc, 1), "clean_s": round(clean_total, 1),
                  "talk_s": round(own.sum() / 100, 1), "tests": tests,
                  "natural_median_s": round(float(np.median(nat_len)), 2) if nat_len else None}
    # konuşma payı pencereleri (RTTM'de konuşma olan her pencere)
    windows = []
    speech = count > 0
    w = int(WIN_S * 100)
    for i in range(0, len(count) - w, w):
        if speech[i:i + w].mean() >= 0.5:
            windows.append(embed(audio[i * SR // 100:(i + w) * SR // 100]))
    return spk, windows


def decide(scores, tau, margin):
    order = np.argsort(scores)[::-1]
    best = scores[order[0]]
    second = scores[order[1]] if len(scores) > 1 else -1.0
    if tau is None or (best >= tau and best - second >= margin):
        return int(order[0])
    return -1


def score(meetings, key, tau, margin, n_enrolled):
    """Toplantılar üzerinden sayımlar. n_enrolled=3 ise her kişi sırayla kayıt dışı bırakılır."""
    c = defaultdict(int)
    for spk in meetings.values():
        ids = sorted(spk)
        groups = [ids] if n_enrolled == len(ids) else [list(g) for g in itertools.combinations(ids, n_enrolled)]
        for g in groups:
            C = np.stack([spk[s]["centroid"] for s in g])
            for gi, s in enumerate(g):
                for e in spk[s]["tests"][key]:
                    d = decide(C @ e, tau, margin)
                    c["member"] += 1
                    c["correct"] += d == gi
                    c["unknown"] += d == -1
                    c["wrong"] += d not in (gi, -1)
            for s in ids:
                if s in g:
                    continue
                for e in spk[s]["tests"][key]:
                    c["impostor"] += 1
                    c["impostor_accepted"] += decide(C @ e, tau, margin) != -1
    return c


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def main():
    t0 = time.perf_counter()
    meetings, windows, speakers = {}, {}, []
    for m in MEETINGS:
        meetings[m], windows[m] = build(m)
        for s, v in meetings[m].items():
            speakers.append({"meeting": m, "speaker": s, "talk_s": v["talk_s"], "clean_s": v["clean_s"],
                             "enroll_s": v["enroll_s"], "natural_median_s": v["natural_median_s"],
                             **{f"n_test_{k}": len(v["tests"][k]) for k in (*TEST_LENS, "natural")}})
        print(f"{m}: hazır ({time.perf_counter() - t0:.0f} sn)", flush=True)

    rows = []
    for n_enr in (4, 3):
        for key in (*TEST_LENS, "natural"):
            top = score(meetings, key, None, None, n_enr)
            row = {"enrolled": n_enr, "test": key if key == "natural" else f"{key:.0f}",
                   "top1": pct(top["correct"], top["member"]), "n": top["member"]}
            for name, (tau, mg) in SETTINGS.items():
                c = score(meetings, key, tau, mg, n_enr)
                row[name] = {"correct": pct(c["correct"], c["member"]), "unknown": pct(c["unknown"], c["member"]),
                             "wrong": pct(c["wrong"], c["member"]),
                             "impostor_accepted": pct(c["impostor_accepted"], c["impostor"])}
            rows.append(row)
            print(row, flush=True)

    # AMI'ye özel ızgara: 3 kayıtlı + 1 kayıtsız, doğal turlar ve 2 sn
    grid = {}
    for key in (2.0, "natural"):
        best = None
        for tau in GRID_TAU:
            for mg in GRID_M:
                c = score(meetings, key, float(tau), float(mg), 3)
                r = {"tau": float(tau), "margin": float(mg), "correct": pct(c["correct"], c["member"]),
                     "unknown": pct(c["unknown"], c["member"]), "wrong": pct(c["wrong"], c["member"]),
                     "impostor_accepted": pct(c["impostor_accepted"], c["impostor"])}
                if r["wrong"] < 2.0 and (best is None or r["unknown"] < best["unknown"]):
                    best = r
        grid[str(key)] = best
        print("ızgara", key, best, flush=True)

    # Konuşma payı (M3): 4 kişi kayıtlı, pencere başına top-1 ve eşikli (unknown sayılmaz)
    share = []
    for m, spk in meetings.items():
        ids = sorted(spk)
        C = np.stack([spk[s]["centroid"] for s in ids])
        W = np.stack(windows[m])
        S = W @ C.T
        top1 = np.bincount(S.argmax(1), minlength=len(ids))
        tau, mg = SETTINGS["LibriSpeech ızgarası"]
        thr = np.zeros(len(ids), int)
        for row in S:
            d = decide(row, tau, mg)
            if d >= 0:
                thr[d] += 1
        true = np.array([spk[s]["talk_s"] for s in ids])
        true_p = 100 * true / true.sum()
        top_p = 100 * top1 / top1.sum()
        thr_p = 100 * thr / max(thr.sum(), 1)
        share.append({"meeting": m, "speakers": ids, "true_pct": true_p.round(1).tolist(),
                      "top1_pct": top_p.round(1).tolist(), "thr_pct": thr_p.round(1).tolist(),
                      "mae_top1_pp": round(float(np.abs(top_p - true_p).mean()), 1),
                      "mae_thr_pp": round(float(np.abs(thr_p - true_p).mean()), 1),
                      "windows": int(len(W)), "unknown_windows_pct": round(100 * (1 - thr.sum() / len(W)), 1)})
        print(share[-1], flush=True)

    out = {"speakers": speakers, "rows": rows, "grid_3enrolled": grid, "share": share,
           "settings": {k: list(v) for k, v in SETTINGS.items()}}
    Path("reports/speaker_id_ami.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"toplam süre: {time.perf_counter() - t0:.0f} sn")


if __name__ == "__main__":
    main()

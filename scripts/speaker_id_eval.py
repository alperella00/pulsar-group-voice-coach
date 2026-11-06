"""Ses parmak izi değerlendirmesi (MIMARI §7, M1/M2) — LibriSpeech test-clean.

Soru: Gruptaki kişi sayısı (N) ve konuşma parçasının uzunluğu (L) arttıkça/azaldıkça
sistem kimin konuştuğunu ne kadar doğru buluyor? Kayıtsız birinin sesini "tanımıyorum" diyebiliyor mu?

Adımlar:
  1. Kayıt: her kişinin ilk bölümünden ~25 sn ses → 2 sn'lik, %50 örtüşen parçalar → her parçanın
     embedding'i (L2 normalize) → ortalama → tekrar normalize = kişinin merkez vektörü.
  2. Test: aynı kişinin KAYITTA KULLANILMAYAN cümlelerinden 1/2/4 sn'lik parçalar (kişi başı 20).
  3. N kişilik rastgele gruplar (her N için 30 grup). Gruptaki herkesin test parçaları gruptaki merkezlerle
     karşılaştırılır. Ayrıca gruba dahil olmayan birinin parçaları ("kayıtsız kişi") da denenir.
  4. Karar kuralları:
       - top1: eşik yok, en benzeri seç.
       - eşikli: en_iyi >= TAU ve en_iyi - ikinci >= MARGIN ise o kişi, değilse "unknown".

Kullanım: uv run python scripts/speaker_id_eval.py
Çıktı: reports/speaker_id_librispeech.md ve .json
"""
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf

ROOT = Path("data/librispeech/LibriSpeech/test-clean")
MODEL = "models/wespeaker_en_voxceleb_resnet34_LM.onnx"
SR = 16000
ENROLL_S = 25.0
CHUNK_S, HOP_S = 2.0, 1.0
TEST_LENS = (1.0, 2.0, 4.0)
TESTS_PER_SPK = 20
GROUP_SIZES = (2, 3, 5, 10, 20, 40)
GROUPS_PER_N = 30
TAU, MARGIN = 0.50, 0.10  # başlangıç değerleri (ARASTIRMA §14); aşağıda ızgara araması da var
SEED = 7

ext = sherpa_onnx.SpeakerEmbeddingExtractor(
    sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=MODEL, num_threads=4))


def embed(x: np.ndarray) -> np.ndarray:
    s = ext.create_stream()
    s.accept_waveform(SR, x)
    s.input_finished()
    v = np.asarray(ext.compute(s), dtype=np.float32)
    return v / np.linalg.norm(v)


def load_speaker(spk_dir: Path):
    """Kişinin bölümlerini sıralı döndürür: [(bölüm, [dosya, ...]), ...]"""
    return [(ch.name, sorted(ch.glob("*.flac"))) for ch in sorted(spk_dir.iterdir()) if ch.is_dir()]


def build_speaker(spk_dir: Path):
    chapters = load_speaker(spk_dir)
    files = [f for _, fs in chapters for f in fs]
    # 1) kayıt: dosya sırasıyla 25 sn dolana kadar (ilk bölümden başlar)
    enroll, used, total = [], set(), 0.0
    for f in files:
        x, _ = sf.read(f, dtype="float32")
        enroll.append(x)
        used.add(f)
        total += len(x) / SR
        if total >= ENROLL_S:
            break
    audio = np.concatenate(enroll)[: int(ENROLL_S * SR)]
    step, size = int(HOP_S * SR), int(CHUNK_S * SR)
    chunk_embs = np.stack([embed(audio[i:i + size]) for i in range(0, len(audio) - size + 1, step)])
    centroid = chunk_embs.mean(0)
    centroid /= np.linalg.norm(centroid)
    sims = chunk_embs @ centroid
    # 2) test: kayıtta kullanılmayan dosyalardan, her uzunluk için ayrı parçalar
    rest = [f for f in files if f not in used]
    tests = {}
    for L in TEST_LENS:
        n = int(L * SR)
        embs = []
        for f in rest:
            x, _ = sf.read(f, dtype="float32")
            if len(x) >= n + int(0.2 * SR):
                embs.append(embed(x[int(0.2 * SR): int(0.2 * SR) + n]))  # baştaki 0,2 sn sessizliği atla
            if len(embs) == TESTS_PER_SPK:
                break
        tests[L] = np.stack(embs)
    return {"centroid": centroid, "self_sim_p5": float(np.percentile(sims, 5)),
            "n_enroll_chunks": len(chunk_embs), "tests": tests, "n_test_files": len(rest)}


def decide(scores: np.ndarray, tau: float | None, margin: float | None) -> int:
    """scores: gruptaki her kişiye benzerlik. Dönen: kişi indeksi veya -1 (unknown)."""
    order = np.argsort(scores)[::-1]
    best = scores[order[0]]
    second = scores[order[1]] if len(scores) > 1 else -1.0
    if tau is None:
        return int(order[0])
    if best >= tau and best - second >= margin:
        return int(order[0])
    return -1


def evaluate(spk, ids, N, L, tau, margin, rng):
    """N kişilik GROUPS_PER_N grup üzerinden sayımlar."""
    c = defaultdict(int)
    groups = [ids] if N == len(ids) else [rng.sample(ids, N) for _ in range(GROUPS_PER_N)]
    for g in groups:
        C = np.stack([spk[s]["centroid"] for s in g])
        for gi, s in enumerate(g):  # gruptaki kişiler
            for e in spk[s]["tests"][L]:
                d = decide(C @ e, tau, margin)
                c["member"] += 1
                c["correct"] += d == gi
                c["unknown"] += d == -1
                c["wrong"] += d not in (gi, -1)
        outsiders = [s for s in ids if s not in g]
        for s in outsiders[:3]:  # kayıtsız kişiler (gruba dahil değil)
            for e in spk[s]["tests"][L][:7]:
                d = decide(C @ e, tau, margin)
                c["impostor"] += 1
                c["impostor_accepted"] += d != -1
    return c


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def main():
    t0 = time.perf_counter()
    ids = sorted(p.name for p in ROOT.iterdir() if p.is_dir())
    spk = {}
    for i, s in enumerate(ids, 1):
        spk[s] = build_speaker(ROOT / s)
        print(f"[{i}/{len(ids)}] {s}: kayıt parçası {spk[s]['n_enroll_chunks']}, "
              f"test dosyası {spk[s]['n_test_files']}", flush=True)
    print(f"embedding süresi: {time.perf_counter() - t0:.0f} sn")

    rows = []
    for N in GROUP_SIZES:
        for L in TEST_LENS:
            top = evaluate(spk, ids, N, L, None, None, random.Random(SEED))
            thr = evaluate(spk, ids, N, L, TAU, MARGIN, random.Random(SEED))
            rows.append({
                "N": N, "L_s": L,
                "top1_acc": pct(top["correct"], top["member"]),
                "thr_correct": pct(thr["correct"], thr["member"]),
                "thr_unknown": pct(thr["unknown"], thr["member"]),
                "thr_wrong_name": pct(thr["wrong"], thr["member"]),
                "impostor_accepted": pct(thr["impostor_accepted"], thr["impostor"]),
                "n_member_trials": thr["member"],
            })
            print(rows[-1], flush=True)

    # Eşik ızgarası: N=3 (demo senaryosu) için, yanlış isim < %2 olan ayarlardan unknown'u en düşük olan
    grid = []
    for L in TEST_LENS:
        best = None
        for tau in np.arange(0.30, 0.71, 0.05):
            for m in np.arange(0.00, 0.31, 0.05):
                c = evaluate(spk, ids, 3, L, float(tau), float(m), random.Random(SEED))
                wrong, unk = pct(c["wrong"], c["member"]), pct(c["unknown"], c["member"])
                imp = pct(c["impostor_accepted"], c["impostor"])
                if wrong < 2.0 and (best is None or unk < best["unknown"]):
                    best = {"L_s": L, "tau": round(float(tau), 2), "margin": round(float(m), 2),
                            "correct": pct(c["correct"], c["member"]), "unknown": unk,
                            "wrong_name": wrong, "impostor_accepted": imp}
        grid.append(best)
        print("ızgara", best, flush=True)

    Path("reports").mkdir(exist_ok=True)
    Path("reports/speaker_id_librispeech.json").write_text(json.dumps(
        {"rows": rows, "grid_N3": grid, "tau": TAU, "margin": MARGIN,
         "self_sim_p5": {s: round(v["self_sim_p5"], 3) for s, v in spk.items()}}, indent=1))

    md = ["# Ses parmak izi: LibriSpeech test-clean (40 konuşmacı)", "",
          f"Model: WeSpeaker ResNet34-LM (ONNX, sherpa-onnx). Kayıt: kişi başı {ENROLL_S:.0f} sn, "
          f"{CHUNK_S:.0f} sn parçalar (%50 örtüşme), ortalama merkez vektör. Test: kayıtta kullanılmayan "
          f"cümlelerden kişi başı {TESTS_PER_SPK} parça. N<40 için {GROUPS_PER_N} rastgele grup.",
          "", f"Eşikli kural: en_iyi ≥ {TAU} ve en_iyi − ikinci ≥ {MARGIN}, değilse `unknown`.", "",
          "| Grup (N) | Parça (sn) | Top-1 doğru (eşiksiz) | Eşikli: doğru | unknown | **yanlış isim** | Kayıtsız kişi kabul edildi |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['N']} | {r['L_s']:.0f} | %{r['top1_acc']} | %{r['thr_correct']} | %{r['thr_unknown']} | "
                  f"**%{r['thr_wrong_name']}** | %{r['impostor_accepted']} |")
    md += ["", "## Eşik ızgarası (N=3, yanlış isim < %2 şartıyla unknown'u en aza indiren)", "",
           "| Parça (sn) | τ | marj | doğru | unknown | yanlış isim | kayıtsız kabul |", "|---|---|---|---|---|---|---|"]
    for g in grid:
        if g:
            md.append(f"| {g['L_s']:.0f} | {g['tau']} | {g['margin']} | %{g['correct']} | %{g['unknown']} | "
                      f"%{g['wrong_name']} | %{g['impostor_accepted']} |")
    md += ["", "Not: LibriSpeech temiz, tek mikrofonlu sesli kitap kaydı. Gerçek toplantı sesinde (AMI) sonuçlar "
           "daha kötü olacak; bu tablo üst sınır olarak okunmalı."]
    Path("reports/speaker_id_librispeech.md").write_text("\n".join(md) + "\n")
    print(f"toplam süre: {time.perf_counter() - t0:.0f} sn")


if __name__ == "__main__":
    main()

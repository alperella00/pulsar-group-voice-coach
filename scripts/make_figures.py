"""reports/*.json'dan README ve rapor için PNG grafikler üretir (reports/figures/)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# dataviz referans paleti (açık mod), kategorik slot 1-3 doğrulanmış sırada
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
OUT = Path("reports/figures")
plt.rcParams.update({"font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


spk = json.loads(Path("reports/speaker_id_librispeech.json").read_text())
rows = spk["rows"]
Ns = sorted({r["N"] for r in rows})
xs = list(range(len(Ns)))

# 1) Doğruluk vs grup büyüklüğü
fig, ax = plt.subplots(figsize=(8, 4.6))
for L, color in ((1.0, ORANGE), (2.0, BLUE), (4.0, AQUA)):
    ys = [next(r["top1_acc"] for r in rows if r["N"] == n and r["L_s"] == L) for n in Ns]
    ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label=f"{L:.0f} sn konuşma")
    ax.annotate(f"{L:.0f} sn", (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", color=INK2)
    i = Ns.index(3)
    dy = 9 if L == 4.0 else -17
    ax.annotate(f"%{ys[i]:.0f}", (xs[i], ys[i]), xytext=(0, dy), textcoords="offset points",
                ha="center", color=INK, fontsize=10)
ax.axvspan(Ns.index(3) - 0.3, Ns.index(3) + 0.3, color=GRID, alpha=0.6, zorder=0)
ax.text(Ns.index(3), 46.5, "demo\nsenaryosu", ha="center", va="bottom", color=INK2, fontsize=9)
ax.set_xticks(xs, [str(n) for n in Ns])
ax.set_xlabel("Gruptaki kişi sayısı")
ax.set_ylabel("Doğru tanıma (%, eşiksiz)")
ax.set_ylim(45, 101)
ax.set_xlim(-0.4, len(Ns) - 0.4)
ax.set_title("Kişi sayısı arttıkça ve konuşma kısaldıkça tanıma zorlaşıyor", loc="left", fontsize=13)
ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.36, 0.02))
style(ax)
fig.text(0.01, 0.01, "LibriSpeech test-clean, 40 konuşmacı · WeSpeaker ResNet34 · kayıt 25 sn",
         color=INK2, fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "speaker_id_vs_group_size.png", dpi=160)

# 2) Eşik ayarı: doğru / unknown / yanlış isim (N=3, 2 sn)
base = next(r for r in rows if r["N"] == 3 and r["L_s"] == 2.0)
tuned = next(g for g in spk["grid_N3"] if g and g["L_s"] == 2.0)
cases = [(f"Izgara ayarı (τ={tuned['tau']}, marj={tuned['margin']})",
          tuned["correct"], tuned["unknown"], tuned["wrong_name"]),
         (f"Başlangıç (τ={spk['tau']}, marj={spk['margin']})",
          base["thr_correct"], base["thr_unknown"], base["thr_wrong_name"])]
fig, ax = plt.subplots(figsize=(8, 2.9))
for i, (name, c, u, w) in enumerate(cases):
    left = 0
    for val, color, lab in ((c, BLUE, "Doğru kişi"), (u, ORANGE, "\"Kim sordu?\" (unknown)"),
                            (w, AQUA, "Yanlış isim")):
        ax.barh(i, val, left=left, color=color, height=0.55, edgecolor=SURFACE, linewidth=2,
                label=lab if i == 0 else None)
        if val >= 10:
            ax.text(left + val / 2, i, f"%{val:.1f}", ha="center", va="center", color="white", fontsize=10)
        left += val
    ax.text(101, i, f"yanlış isim %{w:.1f}", va="center", color=INK, fontsize=10)
ax.set_yticks(range(len(cases)), [c[0] for c in cases])
ax.set_xlim(0, 125)
ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
ax.set_title("3 kişi, 2 sn konuşma: eşik ayarı", loc="left", fontsize=13)
ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.18), fontsize=9)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "speaker_id_threshold_N3.png", dpi=160)

# 3) Kayıtsız kişinin yanlışlıkla kabul edilmesi
fig, ax = plt.subplots(figsize=(8, 3.8))
Ni = [n for n in Ns if n < 40]
for L, color in ((1.0, ORANGE), (2.0, BLUE), (4.0, AQUA)):
    ys = [next(r["impostor_accepted"] for r in rows if r["N"] == n and r["L_s"] == L) for n in Ni]
    ax.plot(range(len(Ni)), ys, color=color, linewidth=2, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label=f"{L:.0f} sn")
ax.set_xticks(range(len(Ni)), [str(n) for n in Ni])
ax.set_xlabel("Gruptaki kişi sayısı")
ax.set_ylabel("Kayıtsız kişi kabul edildi (%)")
ax.set_title("Zayıf nokta: küçük grupta yabancıyı reddetmek (τ=0,5, marj=0,1)", loc="left", fontsize=13)
ax.legend(frameon=False, title="konuşma")
style(ax)
fig.tight_layout()
fig.savefig(OUT / "speaker_id_impostor.png", dpi=160)

# 4) Gemini Live gecikme (TTFB)
gm = [json.loads(l) for l in Path("reports/gemini_turn_test.jsonl").read_text().splitlines()]
labels, vals = [], []
for model, short in (("gemini-3.8-live", "3.8 Live"), ("gemini-2.5-flash-native-audio-preview-12-2025", "2.5 native audio")):
    for k, kname in (("A", "sesli tur, not içinde"), ("B", "sesli tur, not önce"), ("P", "sadece metin (proaktif)")):
        t = sorted(r["ttfb_s"] for r in gm if r["model"] == model and r["kind"] == k)
        labels.append(f"{short} · {kname}")
        vals.append(t[len(t) // 2])
fig, ax = plt.subplots(figsize=(8, 3.8))
colors = [BLUE] * 3 + [ORANGE] * 3
ax.barh(range(len(vals)), vals, color=colors, height=0.6, edgecolor=SURFACE, linewidth=2)
for i, v in enumerate(vals):
    ax.text(v + 0.08, i, f"{v:.2f} sn", va="center", color=INK, fontsize=10)
ax.set_yticks(range(len(labels)), labels)
ax.invert_yaxis()
ax.set_xlabel("Turu kapattıktan ilk ses byte'ına kadar (medyan, sn)")
ax.set_title("Gemini Live: ilk ses gecikmesi", loc="left", fontsize=13)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "gemini_ttfb.png", dpi=160)
print("ok:", sorted(p.name for p in OUT.glob("*.png")))

# 5) LibriSpeech vs AMI (3 kişi kayıtlı, eşiksiz top-1)
ami = json.loads(Path("reports/speaker_id_ami.json").read_text())
cats = ["1", "2", "4", "natural"]
cat_names = ["1 sn", "2 sn", "4 sn", "doğal tur\n(medyan ~2,6 sn)"]
libri = [next(r["top1_acc"] for r in rows if r["N"] == 3 and r["L_s"] == float(c)) if c != "natural" else None
         for c in cats]
amiv = [next(r["top1"] for r in ami["rows"] if r["enrolled"] == 3 and r["test"] == c) for c in cats]
fig, ax = plt.subplots(figsize=(8, 3.9))
w = 0.36
for i, (lv, av) in enumerate(zip(libri, amiv)):
    if lv is not None:
        ax.bar(i - w / 2, lv, w, color=BLUE, edgecolor=SURFACE, linewidth=2, label="LibriSpeech (sesli kitap)" if i == 0 else None)
        ax.text(i - w / 2, lv + 0.6, f"%{lv:.0f}", ha="center", color=INK, fontsize=9)
    ax.bar(i + w / 2, av, w, color=ORANGE, edgecolor=SURFACE, linewidth=2, label="AMI (gerçek toplantı)" if i == 0 else None)
    ax.text(i + w / 2, av + 0.6, f"%{av:.0f}", ha="center", color=INK, fontsize=9)
ax.set_xticks(range(len(cats)), cat_names)
ax.set_ylim(80, 107)
ax.set_yticks([80, 85, 90, 95, 100])
ax.set_ylabel("Doğru tanıma (%, eşiksiz)")
ax.set_title("3 kişilik grup: temiz kayıt ve gerçek toplantı", loc="left", fontsize=13)
ax.legend(frameon=False, loc="upper left", ncol=2)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "speaker_id_libri_vs_ami.png", dpi=160)

# 6) Konuşma payı: gerçek vs tahmin (AMI, 4 toplantı)
fig, axes = plt.subplots(1, 4, figsize=(10, 3.4), sharey=True)
for ax, sh in zip(axes, ami["share"]):
    n = len(sh["speakers"])
    xs4 = range(n)
    ax.bar([x - 0.2 for x in xs4], sh["true_pct"], 0.38, color=BLUE, edgecolor=SURFACE, linewidth=2,
           label="Gerçek (RTTM)")
    ax.bar([x + 0.2 for x in xs4], sh["thr_pct"], 0.38, color=ORANGE, edgecolor=SURFACE, linewidth=2,
           label="Pulsar tahmini")
    ax.set_xticks(list(xs4), [f"K{i + 1}" for i in xs4])
    ax.set_title(f"{sh['meeting']}\nort. hata {sh['mae_thr_pp']} puan", fontsize=10, loc="left")
    style(ax)
axes[0].set_ylabel("Konuşma payı (%)")
axes[0].legend(frameon=False, fontsize=8, loc="upper left")
fig.suptitle("Kim ne kadar konuştu? Gerçek pay ve 1,5 sn'lik pencerelerden tahmin", x=0.01, ha="left", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "talk_share_ami.png", dpi=160)
print("ok: AMI grafikleri")

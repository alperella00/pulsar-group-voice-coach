"""Kullanıcının kendi sesiyle test cümleleri kaydı (K13: test sesi gerçek insan sesi, TTS yok).

Her cümle için: Enter → kayıt başlar, Enter → durur. Kayıtlar data/user/<id>.wav (16 kHz mono, git dışı).
Bir cümleyi tekrar kaydetmek için: uv run python scripts/record_lines.py --only <id>
Mikrofonu seçmek için: --device "MacBook Air Mikrofonu" (Bluetooth kulaklık mikrofonu 8 kHz'e düşüyor, kullanma).
"""
import argparse
import queue
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

SR = 16000
OUT = Path("data/user")

# (id, ne test ediyor, söylenecek cümle)
LINES = [
    # Tanıtım: ses parmak izi kaydı + prosodi normali + profil (CEFR, ilgi alanları). Rahat, doğal, ~25 sn.
    ("intro", "kayıt (tanıtım, ~25 sn)",
     "Hi Pulsar, I'm Alper. [Kendini serbestçe İngilizce tanıt: ne iş yapıyorsun, neler seversin, hafta sonu ne yaptın. "
     "Okuma, konuşur gibi anlat, ~25 saniye.]"),
    # Kural 1: isim geçiyor (başta, ortada, sonda)
    ("name_start", "kural 1: isim başta", "Hey Pulsar, how are you today?"),
    ("name_start2", "kural 1: isim başta", "Pulsar, what do you think about working from home?"),
    ("name_end", "kural 1: isim sonda", "What should we talk about next, Pulsar?"),
    ("name_mid", "kural 1: isim ortada", "I think, Pulsar, you could give us a new topic."),
    ("name_fast", "kural 1: hızlı ve yutarak", "[Hızlı ve gelişigüzel söyle] Pulsar can you help me with a word?"),
    # Kural 2: takip (Pulsar cevap verdikten sonra, isim yok)
    ("follow1", "kural 2: takip, isim yok", "Good, thanks. What did you do today?"),
    ("follow2", "kural 2: takip, isim yok", "I'm a software engineer, I work on data projects."),
    # Kural 3: soru, isim yok
    ("question", "kural 3: soru, isim yok", "What's the difference between since and for?"),
    # Negatifler: Pulsar'a hitap YOK, ama tuzak var
    ("neg_pulsars", "negatif: kelime geçiyor ama hitap değil", "I read an article about pulsars and neutron stars."),
    ("neg_pulse", "negatif: benzer ses", "My pulse was really fast after the run."),
    ("neg_other", "negatif: başkasına hitap", "Mehmet, what do you think about it?"),
    ("neg_plain", "negatif: düz cümle", "I think we should take a short break now."),
    # Prosodi: aynı cümle normal ve zorlanarak
    ("pros_normal", "prosodi: normal", "Last weekend I went to the seaside with my friends and we had a great time."),
    ("pros_slow", "prosodi: zorlanarak",
     "[Aynı cümle, yavaş ve duraksayarak, kelime arıyormuş gibi; 'uh, um' ekleyebilirsin] "
     "Last weekend I went to the seaside with my friends and we had a great time."),
]


def record(device) -> np.ndarray:
    q: queue.Queue = queue.Queue()
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=device,
                        callback=lambda d, f, t, s: q.put(d.copy())):
        input("   ● KAYITTA. Bitince Enter'a bas.")
    chunks = []
    while not q.empty():
        chunks.append(q.get())
    return np.concatenate(chunks)[:, 0] if chunks else np.zeros(0, np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="MacBook Air Mikrofonu")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [l for l in LINES if not args.only or l[0] in args.only]
    print(f"Mikrofon: {args.device}. {len(lines)} cümle. Köşeli parantez içindekiler talimat, okunmaz.\n")
    for i, (lid, what, text) in enumerate(lines, 1):
        print(f"[{i}/{len(lines)}] {lid}  ({what})\n   “{text}”")
        input("   Hazır olunca Enter → kayıt başlar.")
        x = record(args.device)
        peak = float(np.abs(x).max()) if len(x) else 0.0
        sf.write(OUT / f"{lid}.wav", x, SR)
        warn = "  ⚠ çok kısık, mikrofona yaklaş ve tekrar kaydet" if peak < 0.05 else (
            "  ⚠ çok yüksek (kırpılma), biraz uzaklaş" if peak > 0.98 else "")
        print(f"   kaydedildi: {OUT / (lid + '.wav')}  {len(x) / SR:.1f} sn, tepe {peak:.2f}{warn}\n")
    print("Bitti. Tekrar kaydetmek için: uv run python scripts/record_lines.py --only <id>")


if __name__ == "__main__":
    main()

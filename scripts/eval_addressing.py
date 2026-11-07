"""Hitap kurallarını kullanıcının kayıtlarıyla test eder (gerçek ses → ASR → kurallar).

A) Tek tek, bağlam yok: her cümle sohbetin ortasında birden söylenmiş gibi.
B) Senaryo: kayıtlar bir sohbet akışına diziliyor; Pulsar'ın cevapları simüle ediliyor (Gemini bağlı değil).
Kullanım: uv run python scripts/eval_addressing.py
"""
import sys

import soundfile as sf

sys.path.insert(0, "src")
from pulsar.addressing import Addressing  # noqa: E402
from pulsar.asr import ASR  # noqa: E402

PEOPLE = ["Alper", "Mehmet", "Ayse"]
# beklenen: tek başına söylendiğinde Pulsar'a mı?
EXPECT_A = {"name_start": True, "name_start2": True, "name_end": True, "name_mid": True, "name_fast": True,
            "follow1": False, "follow2": False, "question": False, "neg_pulsars": False, "neg_pulse": False,
            "neg_other": False, "neg_plain": False}

# (kayıt, konuşan, bir önceki olaydan sonra kaç sn sonra başlıyor, beklenen, açıklama)
# "PULSAR" satırları: Pulsar cevap veriyor (süre sn, soruyla mı bitti)
SCENARIO = [
    ("name_start", "Alper", 0.0, True, "isimle hitap"),
    ("PULSAR", 4.0, True),
    ("follow1", "Alper", 1.0, True, "takip penceresi (8 sn), isim yok"),
    ("PULSAR", 4.0, False),
    ("follow2", "Alper", 2.0, True, "takip penceresi (4 sn)"),
    ("PULSAR", 4.0, True),
    ("neg_other", "Alper", 1.0, False, "pencere açık ama Mehmet'e soruyor"),
    ("neg_plain", "Mehmet", 3.0, False, "başka kişi, düz cümle"),
    ("question", "Mehmet", 2.0, True, "soru + son 30 sn'de hitap var"),
    ("PULSAR", 5.0, False),
    ("neg_pulse", "Alper", 20.0, False, "pencere kapandı, düz cümle"),
    ("neg_pulsars", "Alper", 15.0, False, "'pulsars' çoğul, hitap değil"),
    ("question", "Alper", 40.0, False, "soru ama son 30 sn'de hitap yok"),
    ("name_end", "Alper", 5.0, True, "isim sonda"),
]


def main():
    asr = ASR()
    asr.warmup()
    text = {}
    for k in list(EXPECT_A):
        x, _ = sf.read(f"data/user/{k}.wav", dtype="float32")
        text[k] = asr.pool.submit(asr.transcribe, x).result().text

    print("A) Tek tek (bağlam yok)\n")
    ok = 0
    for k, exp in EXPECT_A.items():
        d = Addressing(PEOPLE).decide(text[k], "Alper", 100.0)
        good = d.addressed == exp
        ok += good
        print(f"  {'✓' if good else '✗'} {k:<12} beklenen {'EVET ' if exp else 'HAYIR'} → {'EVET ' if d.addressed else 'HAYIR'}"
              f"  [{d.rule}{': ' + d.detail if d.detail else ''}]  “{text[k]}”")
    print(f"\n  {ok}/{len(EXPECT_A)} doğru")

    print("\nB) Senaryo (Pulsar'ın cevapları simüle)\n")
    ad = Addressing(PEOPLE)
    t, ok, n = 0.0, 0, 0
    for row in SCENARIO:
        if row[0] == "PULSAR":
            _, dur, asked = row
            t += dur
            ad.on_reply(last_speaker, t, asked)
            print(f"  {t - dur:5.1f}-{t:5.1f} sn  Pulsar cevap veriyor{' (soruyla bitiyor)' if asked else ''}")
            continue
        k, who, gap, exp, why = row
        t += gap
        d = ad.decide(text[k], who, t)
        if d.addressed:
            last_speaker = who
        dur = sf.info(f"data/user/{k}.wav").duration
        good = d.addressed == exp
        ok, n = ok + good, n + 1
        print(f"  {'✓' if good else '✗'} {t:5.1f} sn  {who:<6} “{text[k]}”\n"
              f"{'':16}beklenen {'EVET ' if exp else 'HAYIR'} → {'EVET ' if d.addressed else 'HAYIR'}"
              f" [{d.rule}{': ' + d.detail if d.detail else ''}]  ({why})")
        t += dur
    print(f"\n  {ok}/{n} doğru")


if __name__ == "__main__":
    main()

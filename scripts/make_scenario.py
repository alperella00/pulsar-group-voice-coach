"""Uçtan uca replay testi için senaryo sesi: kullanıcının kayıtları + sessizlikler → data/user/scenario.wav + .rttm

AMI'de kimse "Pulsar" demiyor; Gemini yolunu uçtan uca denemek için kullanıcının kendi kayıtlarını bir sohbet
akışına diziyoruz. Hitap edilen cümlelerden sonra Pulsar'ın cevabı için boşluk bırakılıyor (replay sırasında Pulsar
konuşuyor). RTTM'yi biz yazıyoruz (kayıt RTTM'den: konuşmacı "Alper", ilk 25 sn = tanıtım).
"""
import numpy as np
import soundfile as sf

SR = 16000
# (kayıt, sonrasında kaç sn sessizlik)
FLOW = [
    ("intro", 2.0),
    ("name_start", 9.0),     # → Pulsar cevap verir (soruyla bitirirse takip penceresi 8 sn)
    ("follow1", 9.0),        # takip: isim yok
    ("neg_plain", 2.0),      # Pulsar'a değil (pencere bu sırada kapanmış olabilir)
    ("neg_pulse", 3.0),      # tuzak
    ("name_end", 9.0),       # isim sonda
    ("neg_pulsars", 3.0),    # tuzak (çoğul)
    ("question", 3.0),       # soru; son 30 sn'de hitap varsa Pulsar'a gider
    ("pros_slow", 9.0),
]


# söz kesme testi: Pulsar cevap verirken (ilk ses ~1,5 sn + cevap ~5 sn) isimle tekrar sesleniliyor
FLOW_BARGE = [
    ("intro", 9.0),
    ("name_start2", 3.5),    # → Pulsar cevaba başlar
    ("name_end", 12.0),      # Pulsar konuşurken "…, Pussar?" → söz kesme
    ("neg_plain", 3.0),
]


def main():
    import sys
    flow, out = (FLOW_BARGE, "scenario_barge") if "--barge" in sys.argv else (FLOW, "scenario")
    parts, rttm, t = [], [], 0.0
    for name, gap in flow:
        x, sr = sf.read(f"data/user/{name}.wav", dtype="float32")
        assert sr == SR
        parts += [x, np.zeros(int(gap * SR), np.float32)]
        rttm.append(f"SPEAKER scenario 1 {t:.2f} {len(x) / SR:.2f} <NA> <NA> Alper <NA> <NA>")
        t += len(x) / SR + gap
    sf.write(f"data/user/{out}.wav", np.concatenate(parts), SR)
    open(f"data/user/{out}.rttm", "w").write("\n".join(rttm) + "\n")
    print(f"data/user/{out}.wav: {t:.1f} sn, {len(flow)} kayıt")


if __name__ == "__main__":
    main()

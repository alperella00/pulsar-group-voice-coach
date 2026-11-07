# Hitap: ASR "Pulsar"ı nasıl yazıyor? (2026-11-07)

**Veri:** Kullanıcının kendi sesi, 15 cümle, telefonda WhatsApp sesli mesajı (Opus, 48 kHz → 16 kHz WAV).
`data/user/*.wav` (git dışı), cümle listesi `scripts/record_lines.py`. ASR: parakeet-tdt-0.6b-v3.

ASR 15 kaydın hepsini doğru sırayla, büyük ölçüde doğru yazdı (tanıtımda isim "Alper" → "Altar" oldu).

## "Pulsar" en yakın kelime ve Levenshtein uzaklığı

| Kayıt | Greedy (şu an) | lev | Beam + boost 2 | Beam + boost 5 |
|---|---|---|---|---|
| name_start | Hey **Pussar**, how are you today? | 1 | Pulsar (? düştü) | Pulsar |
| name_start2 | **Pulsar**, what do you think… | 0 | Pulsar | Pulsar |
| name_end | …next, **Pussar**? | 1 | Pulsar (? düştü) | pulsar |
| name_mid | I think, **Pulsar**, uh… | 0 | Pulsar | pulsar |
| name_fast | **Pussar**, can you help me… | 1 | Pussar | Pulsar |
| neg_pulsars | …about **pulsars** and neutron stars | 1 | pulsars | **pulsar** (yanlış) |
| neg_pulse | My **pulse** was really fast… | **2** | pulse | **"My pulsar was…"** (halüsinasyon) |
| neg_other / neg_plain / follow1 / question | — | 5 | — | — |

Boost 10: tamamen bozuldu ("Pulsar pulsar pulsar a short break now.").

## Ne öğrendik?
1. **Model "Pulsar"ı bilmiyor:** 5'te 3 "Pussar". Bulanık eşleşme şart.
2. **Levenshtein ≤ 2 (MIMARI'deki plan) "pulse"u yakalıyor** → yanlış tetiklenme. ≤ 1: isimli 5/5, "pulse" elenir.
3. **"pulsars" (çoğul, gerçek kelime) ≤ 1'e takılıyor** → ayrı kural gerekiyor.
4. **Kelime güçlendirme iki ucu keskin:** ağırlık 2 isimleri düzeltiyor ama soru işaretlerini düşürüyor (soru kuralı
   noktalamaya dayanıyor); ağırlık ≥ 5 olmayan yerde "Pulsar" duyuyor. Modelin olasılığını dışarıdan itmenin riski.
5. Örnek küçük (tek konuşmacı, 15 cümle): sonuçlar yön gösterici, kesin değil.

**Not:** Kayıtlar ana dili İngilizce olmayan, aksanlı bir konuşmacıdan. Bu, hedef kullanıcıya (dil öğrenen) yakın
bir koşul; ama "Pussar"ın sebebi (aksan / telefon mikrofonu / modelin kelimeyi bilmemesi) tek kişiyle ayrılamaz.
Ses günden güne değişebildiği için canlı kullanımda kayıt aynı oturumun başında yapılmalı.

## Hitap kuralları testi (K21, `src/pulsar/addressing.py`, `scripts/eval_addressing.py`)

Gerçek ses → ASR → kurallar. Pulsar'ın cevapları simüle (Gemini bağlı değil).

- **A) Tek tek, bağlam yok:** 12/12. İsimli 5 cümle EVET (3'ü "Pussar" üzerinden), takip/soru/tuzaklar HAYIR;
  "Mehmet, what do you think" → `other_person` kuralıyla HAYIR.
- **B) Senaryo (10 tur):** 10/10. Takip penceresi (8 sn soruyla / 4 sn), pencere açıkken başkasına soru (HAYIR),
  başka kişinin sorusu + son 30 sn'de hitap (EVET), pencere kapandıktan sonra soru (HAYIR).

**Sınır:** Eşik (≤ 1), çoğul kuralı ve senaryo bu kayıtlar görüldükten sonra yazıldı. Sonuç kuralların tasarlandığı
gibi çalıştığını gösteriyor, görülmemiş cümlelerdeki başarıyı değil. Ayrı bir test seti gerekir.
Bilinen açıklar: "Pulsar"a benzeyen başka bir isim/kelime (1 harf farkla); takip penceresinde aynı kişinin
başkasına isim vermeden soru sorması; ASR ismi 2+ harf bozarsa kaçırma.

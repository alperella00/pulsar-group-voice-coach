# Prosodi ve ton notu (2026-11-07)

Kod: `src/pulsar/prosody.py` (ölçüm + kişinin normaline göre z-skor + durum), `src/pulsar/coach.py` (ton satırı),
test `scripts/eval_tone.py` (M6). Veri: kullanıcının kayıtları (`data/user/`, telefon, tek kişi).

## Kişinin normali (tanıtım, 6 × 5 sn parça)
hız 3,40 ± 0,40 hece/sn · MLR 16,7 ± 1,7 hece · tur içi ≥ 250 ms duraksama yok · F0 98 Hz.
Not: tanıtım **okundu**; okuma serbest konuşmadan akıcı, yani "normal" hız olduğundan yüksek ölçülmüş olabilir.

## Turların durumu (MLR düzeltmesinden sonra)

| Kayıt | Hız (z) | Duraksama / dolgu | Durum |
|---|---|---|---|
| pros_normal | 3,63 (+0,57) | 0 / 0 | normal |
| **pros_slow** (bilerek yavaş, duraksayarak) | 2,73 (−1,68) | 1 (480 ms) / 1 | **struggling** |
| name_start2, name_end, follow1 | 2,50-2,86 (−1,3…−2,3) | 0 / 0 | slightly_slow |
| diğer 7 kısa cümle | | | normal |

**Bulunan hata ve düzeltme:** İlk sürümde normal hızdaki kısa sorular da "kısa koşu" sinyali verdi. Duraksamasız
kısa turda MLR = turun toplam hecesi (ör. 10), tanıtımın 5 sn'lik parçalarında ~17. MLR artık sadece turda en az bir
duraksama varsa kullanılıyor. Kalan 3 "slightly_slow" kısa turlarda hızın oynaklığından (80 ms kelime zamanları) ve
okunmuş tanıtımın yüksek normalinden geliyor olabilir; bedeli düşük (sadece "biraz daha kısa cümle"), kurala bu
kayıtlara göre daha fazla ayar yapılmadı.

## M6: Ton talimatı Pulsar'ı gerçekten yavaşlatıyor mu?

Aynı tur (pros_slow) Gemini 3.8 Live'a 5 kez normal notla, 5 kez "struggling" notuyla ("~25% slower, natural pauses,
very short sentences") gönderildi; her deneme ayrı oturum. Pulsar'ın sesi kendi ASR'mizle yazıya döküldü, aynı
prosodi koduyla ölçüldü. Ham kayıtlar `reports/tone_test.jsonl`, sesler `logs/replies/tone_*.wav`.

| Not | n | Hız (hece/sn) | Süre | Kelime | Kelime/cümle | Duraksama |
|---|---|---|---|---|---|---|
| normal | 5 | 4,23 (3,52-4,55) | 5,3 sn | 17,0 | 8,5 | 0 |
| struggling | 5 | 3,95 (3,57-4,53) | 4,9 sn | 15,6 | 7,8 | 0 |

**Sonuç:** etki zayıf: hız ~%7 düştü (istenen %25), aralıklar iç içe, n=5 ile ayırt edilemez; istenen duraksamalar
hiç yok. Gemini'de hız parametresi yok ve doğal dil talimatı hızı güvenilir şekilde değiştirmiyor (K6'daki risk
gerçekleşti). Ayrıca bir önceki denemede 6 cevaptan 1'inde model 30 sn sessiz kaldı (proactive audio).
**Çözüm adayları:** Pulsar'ın sesini lokal olarak perdeyi bozmadan yavaşlatmak (time-stretch, ör. WSOLA; akış
halinde yapmak ek iş) ya da hız parametresi olan bir S2S (OpenAI Realtime `speed`).

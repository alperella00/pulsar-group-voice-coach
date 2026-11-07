# Uçtan uca: kullanıcının sesi → Pulsar'ın sesli cevabı (2026-11-07)

**Komut:** `uv run python scripts/make_scenario.py` → `uv run python -m pulsar --wav data/user/scenario.wav
--rttm data/user/scenario.rttm --gemini [--play] --log logs/scenario.jsonl`. Cevap sesleri `logs/replies/*.wav`.

**Kurgu:** Kullanıcının 9 kaydı (tanıtım + 8 cümle) aralarına 2-9 sn sessizlik konarak tek WAV'a dizildi (113 sn).
Tek kayıtlı kişi (Alper; kayıt RTTM'den, tanıtımın ilk 25 sn'si). Replay gerçek zamanda, Gemini 3.8 Live canlı.
Not: replay Pulsar'ı beklemiyor; sessizlikler sabit olduğu için bazı cümleler Pulsar konuşurken geldi.

## Ne oldu (terminal çıktısından)

| Cümle | Hitap kararı | Pulsar |
|---|---|---|
| Tanıtım ("Hi Pulsar, I'm Alper…", 30 sn) | EVET (isim) | "It's great to meet you, Alper! … What kind of side project were you working on?" |
| "Hey pulsar, how are you today?" | EVET (isim) | atlandı: Pulsar hâlâ tanıtıma cevap hazırlıyordu (WAITING) |
| "Good, thanks. What did you do today?" | EVET (soru + son 30 sn'de hitap) | "I've been preparing to chat with all of you today. Did you get to relax at all today, Alper?" |
| "I think we should take a short break now." | EVET (takip, 2,7 sn) | "That sounds like a good idea, Alper. I'll be right here when you're ready to continue." |
| "My pusse was really fast after the run." | EVET (takip, 7,7 sn) | atlandı: Pulsar konuşuyordu |
| "What should we talk about next, Pussar?" | EVET (isim, "Pussar") | "We could discuss your favorite movies or maybe travel plans. …" |
| "I read an article about pulsars and neutron stars." | HAYIR (çoğul) | — |
| "What's the difference between since and for?" | EVET (takip, 7,1 sn) | "We use 'for' to measure a duration of time and 'since' for a specific starting point. Does that difference make sense to you, Alper?" |
| "Last weekend I went to the uh seaside…" (yavaş) | HAYIR (pencere kapalı) | — |

- Pulsar **4/4 cevapta ismiyle hitap etti**; isim sadece COACH NOTE'ta vardı. Tanıtımdaki bilgiyi (side project) kullandı.
- Takip penceresi tasarlandığı gibi çalıştı. "Take a short break" ve "since/for" cümleleri senaryoda Pulsar'a
  yönelik yazılmamıştı ama Pulsar'ın soruyla biten cevabının hemen ardından geldikleri için kural EVET dedi;
  içerik olarak da Pulsar'a cevap gibi okunuyorlar ve Pulsar mantıklı cevap verdi.

## Gecikme (kişinin susmasından Pulsar'ın ilk sesine)

| Tur | Tur sonu → gönderim (VAD 0,5 sn + ASR + bölme) | Gemini ilk ses | Toplam |
|---|---|---|---|
| tanıtım (30 sn) | 2,21 sn | 9,00 sn | 11,2 sn |
| 2 | 0,61 | 1,38 | **1,99 sn** |
| 3 | 1,18 | 1,31 | 2,49 sn |
| 5 | 1,38 | 1,43 | 2,81 sn |
| 7 | 1,09 | 1,57 | 2,66 sn |

Kısa turlarda toplam **2,0-2,8 sn** (hedef 1,5 sn). Lokal kısım 0,6-1,4 sn: ASR'nin gerçek zamandaki yavaşlaması
(reports/asr_parakeet.md) burada görünüyor. 30 sn'lik tanıtımda Gemini 9 sn düşündü: uzun sesi işlemek pahalı.

## Görülen sorunlar
1. Tanıtım Pulsar'a hitap sayılıp gönderildi (içinde "Hi Pulsar" var). Canlıda tanıtım ayrı bir aşama olmalı:
   Pulsar herkesi tek tek karşılar, cevabı tanıtımlar bitince verir (ya da tanıtıma hiç cevap vermez).
2. Pulsar meşgulken gelen hitaplar atlanıyor; kişi tekrar sormak zorunda. Kuyruk ya da "kesme" (barge-in) yok.
3. Tek kişi kayıtlı olduğundan konuşmacı tanıma burada sınanmadı (fark değerleri anlamsız: ikinci profil yok).

# Gemini Live risk testi (2026-11-06)

Script: `scripts/gemini_turn_test.py`. Test sesi: LibriSpeech test-clean `1089-134686-0001` (gerçek insan, 3,27 sn).
Her deneme ayrı oturum, her tür 3 deneme. TTFB = turu kapattıktan (`activity_end` / `turn_complete`) ilk ses byte'ına kadar geçen süre.

- **A**: COACH NOTE aktivite penceresinin içinde (`send_realtime_input(text=…)`)
- **B**: COACH NOTE turdan önce (`send_client_content(…, turn_complete=False)`)
- **P**: Ses yok, sadece metin talimatı (proaktif soru)

| Model | Tür | Cevap geldi | Notu kullandı (isim) | TTFB medyan (min–maks) | Cevap süresi medyan |
|---|---|---|---|---|---|
| gemini-3.8-live | A | 3/3 | 3/3 | 1.59 sn (1.59–1.67) | 6.1 sn |
| gemini-3.8-live | B | 3/3 | 3/3 | 1.75 sn (1.66–2.16) | 5.5 sn |
| gemini-3.8-live | P | 3/3 | 3/3 | 0.60 sn (0.55–0.62) | 4.4 sn |
| gemini-2.5-flash-native-audio-preview-12-2025 | A | 3/3 | 3/3 | 6.87 sn (6.43–7.09) | 4.2 sn |
| gemini-2.5-flash-native-audio-preview-12-2025 | B | 3/3 | 0/3 | 5.18 sn (4.84–5.91) | 5.0 sn |
| gemini-2.5-flash-native-audio-preview-12-2025 | P | 3/3 | 3/3 | 2.38 sn (1.67–2.64) | 2.5 sn |

Ham kayıtlar: `reports/gemini_turn_test.jsonl` (cevap metinleri dahil).

## Yorum

1. **3.8 Live 9/9 cevap verdi.** Kapatılamayan proactive audio özelliğinden korktuğumuz "sessiz kalma" durumu bu
   küçük örnekte hiç görülmedi. Örnek küçük olduğu için tur yöneticisindeki `WAITING` zaman aşımı yine de kalıyor (M7).
2. **COACH NOTE için A yolu seçildi.** 3.8'de iki yol da çalıştı, ama A biraz daha hızlı ve daha tutarlı (1,59–1,67 sn).
   2.5'te B yolu notu **tamamen yok saydı** (0/3). Turdan önce ayrı bir mesaj olarak gelen not, modele göre farklı
   davranıyor. Notu turun içinde göndermek daha sağlam.
3. **2.5 native audio yedek olarak bile zayıf:** Sesli turda TTFB 5–7 sn.
4. **Gecikme:** 3.8'de sesli turda TTFB ~1,6 sn, sadece metinle ~0,6 sn. Aradaki ~1 sn sesi işlemenin maliyeti.
   Bizim VAD ve lokal işlem süremiz (~0,5–0,7 sn) eklenince kişinin susmasından Pulsar'ın konuşmasına kadar
   ~2,2 sn çıkıyor. Bu, 1,5 sn hedefinin üstünde. Denenecekler:
   - düşük düşünme seviyesi (bu testte ayarlanmadı),
   - daha kısa not.
5. **Kalite:** Cevaplar 2 cümle oldu, isimle hitap etti, kolay bir soruyla bitti. Yani talimata uydu.
   "~25% slower" talimatının etkisi ise henüz ölçülmedi (M6).

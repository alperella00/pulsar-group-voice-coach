# Durum: nerede kaldık, sırada ne var

> Bu dosya her çalışma oturumunun sonunda güncellenir. Yeni bir sohbet önce bunu okur, sonra gerekiyorsa
> `MIMARI.md` (sistem), `KARARLAR.md` (K1–K17) ve `reports/README.md`'ye (bulgular) bakar.

**Son güncelleme:** 2026-11-06 gece (AMI testi bitti)

## Kısaca proje
Pulsar: 3-4 kişilik online İngilizce konuşma grubunda kimin konuştuğunu ses parmak iziyle, nasıl konuştuğunu
prosodiyle bulan ve sadece kendisine hitap edilen turları, bir COACH NOTE ile birlikte Gemini 3.8 Live'a
(speech-to-speech) gönderen bir koç. Dinleme modu: C-lite (K3).

## Yapılanlar
| Tarih | Ne | Sonuç / dosya |
|---|---|---|
| 11-06 | Mimari, kararlar, araştırma | `MIMARI.md`, `KARARLAR.md` K1–K16, `ARASTIRMA.md` |
| 11-06 | `uv` projesi, `google-genai`, `sherpa-onnx` | `pyproject.toml` |
| 11-06 | **Gemini Live risk testi** | 3.8 Live (v1beta) 9/9 cevap verdi, not turun içinde gönderilmeli, TTFB ~1,6 sn → K17, `reports/gemini_turn_test.md` |
| 11-06 | **Ses parmak izi, LibriSpeech** | 3 kişi / 2 sn: %95 (eşiksiz); ızgara ayarı τ=0,3, marj=0,05 → doğru %91, unknown %8, yanlış isim %1,4. Zayıf nokta: kayıtsız kişi %30+ kabul. `reports/speaker_id_librispeech.md` |
| 11-06 | Okunur bulgular + grafikler | `reports/README.md`, `reports/figures/`, `scripts/make_figures.py` |
| 11-06 | AMI verisi indirildi | `data/ami/audio/{ES2004a,IS1009a,TS3003a,EN2002a}.Mix-Headset.wav` + `data/ami/rttm/` (gitignored) |
| 11-06 | **Ses parmak izi + konuşma payı, AMI** | 3 kayıtlı, doğal tur (medyan 2,6 sn): %96 eşiksiz. Eşik taşınmıyor: LibriSpeech ayarı (0,3/0,05) AMI'de yanlış isim %2,4, kayıtsız kabul %32; AMI ayarı **τ=0,45, m=0,05** → doğru %88,8, unknown %9,4, yanlış %1,9, kayıtsız %10. Konuşma payı hatası 2-6 puan. `reports/speaker_id_ami.md`, `reports/README.md` §3 |

## Ortam notları
- `.env` içinde `GEMINI_API_KEY` (ücretsiz katman). Key'i yazdırma.
- Gemini: 3.8 Live → `api_version="v1beta"`; 2.5 native audio → yalnızca `v1alpha` (yedek, yavaş).
- Embedding modeli: `models/wespeaker_en_voxceleb_resnet34_LM.onnx` (gitignored). Yeniden indirmek için:
  `https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx`
- Veri `data/` altında (gitignored): LibriSpeech test-clean, AMI 4 toplantı.
- Komutlar: `uv run python scripts/<isim>.py`. Shell'de başka bir projenin `VIRTUAL_ENV`'i açık kalmışsa önce `unset VIRTUAL_ENV`.
- **Test sesi her zaman gerçek insan sesi** (LibriSpeech/AMI). TTS yok, smoke testte bile (K13).

## Sırada
1. **Kullanıcıya sorulacak:** Demoda hangi eşik kullanılsın? Aday: AMI ayarı τ=0,45, m=0,05 (henüz karar değil;
   kayıtsız kişi araştırması gelince kesinleşecek).
2. İskelet: ses I/O, Silero VAD ile tur kesme, replay modu, JSONL olay günlüğü (MIMARI §9).
3. Gemini'de düşük düşünme ayarıyla TTFB'yi tekrar ölçmek.

## Açık konular
- **Kayıtsız kişiyi reddetme:** Kullanıcı deep research yaptıracak, istek metni hazır:
  `docs/ARASTIRMA_ISTEGI_kayitsiz_kisi.md`. Sonuç gelince AS-norm / kişiye özel eşik denenecek.
- Gecikme hedefi (1,5 sn) şu an ~2,2 sn: düşünme ayarı ve not uzunluğu denenecek.
- Ton talimatının ("~25% slower") sesli çıktıyı gerçekten değiştirip değiştirmediği (M6) henüz ölçülmedi.

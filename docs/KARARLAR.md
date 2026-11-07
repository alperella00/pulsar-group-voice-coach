# Kararlar

Her kararda değerlendirilen seçenekler, seçilen seçenek ve gerekçesi yazılı. Kaynaklar `docs/ARASTIRMA.md`'de.

---

### K1. Kendi S2S modelimizi eğitmiyoruz (2026-11-06)
- **Seçenekler:** Kendi modelimizi eğitmek / hazır bir S2S model kullanıp etrafına sistem kurmak.
- **Seçilen:** Hazır model + kendi sistemimiz.
- **Neden:** Elimizde 3 gün ve 8 GB RAM var. Ayrıca projenin değeri modeli eğitmekte değil, modeli bir ürüne
  bağlamakta: kimin konuştuğunu bilmek, tonu ayarlamak, turu yönetmek.

### K2. Senaryo: online grup görüşmesi, kulaklık, tek karışık ses akışı (2026-11-06)
- **Seçenekler:** Masadaki tek bir telefon (oda yankısı var) / online görüşme ve kulaklık.
- **Seçilen:** Online görüşme. Herkes kulaklık takıyor. Pulsar bütün sesi tek bir karışık akış olarak alıyor ve kendi
  sesi bu akışa karışmıyor.
- **Neden:** Yankı engelleme 3 günlük bir demonun kapsamı dışında. Tek karışık akış ise ses parmak izini gerekli
  kılıyor: kanal başına ayrı ses gelseydi kimin konuştuğu zaten belli olurdu.

### K3. Dinleme modu: C-lite (2026-11-06)
- **Seçenekler:**
  - A) Wake word ("Hey Pulsar").
  - B) Bütün sesi sürekli S2S modele göndermek, konuşup konuşmamaya model karar verir.
  - C) Hitap kararı lokal: tur sonunda lokal ASR + konuşmacı + kurallar.
- **Seçilen:** C-lite. Sürekli streaming ASR yok, her tur bitince yazıya dökülüyor.
- **Neden:**
  - A: Porcupine'in ücretsiz katmanı kapandı, openWakeWord'ün eğitimi ise saatler süren GPU işi ve ~20 GB disk istiyor.
  - B: Model, tek karışık akışta kimin konuştuğunu bilemez. Ayrıca bizim prosodi notumuzu her tura ekleyemeyiz.
  - C: Tur kontrolü bizde kalıyor, sohbetin konusunu biliyoruz, maliyet düşük.
  - "Lite" olmasının nedeni: parakeet-mlx bir turu ~0,15 sn'de yazıya döküyor, streaming kurmaya gerek yok.

### K4. Turu biz yönetiyoruz, spekülatif gönderim yok (2026-11-06)
- **Seçilen:** Gemini'nin otomatik tur tespiti kapalı (`activityStart`/`activityEnd`). Tur, hitap kararı verilene kadar
  lokal tamponda bekliyor ve karar "evet" ise tek seferde gönderiliyor.
- **Neden:** Model cevaba başlamadan önce kimin konuştuğunu ve nasıl cevap vermesi gerektiğini bilmeli. Gemini'de
  gönderilmiş bir turu geri çekmenin yolu yok, bu yüzden yanlışlıkla gönderilen bir tur modelin bağlamında kalırdı.

### K5. S2S sağlayıcısı: Gemini 3.8 Live, ücretsiz katman (2026-11-06)
- **Seçenekler:** Gemini 3.8 Live / Gemini 2.5 native audio / OpenAI gpt-realtime-2.1(-mini) / Amazon Nova 2 Sonic /
  Hume EVI / Moshi.
- **Seçilen:** Gemini 3.8 Live, ücretsiz key ile. Yedek: 2.5 native audio. OpenAI sadece zaman kalırsa karşılaştırma için.
- **Neden:** Manuel tur yönetimi, oturum ortasında metin ekleme ve sadece metinden sesli cevap üretme özelliklerinin
  hepsi var, üstelik ücretsiz. Diğerleri neden elendi:
  - Nova Sonic: AWS hesabı ister, tamamen manuel tur modu belgelenmemiş.
  - Hume EVI: Manuel tur desteği doğrulanamadı.
  - Moshi: Talimat ve bağlam alamıyor.
- **Bilinen risk:** 3.8'de proactive audio kapatılamıyor, model hitap edilen bir tura sessiz kalabilir. Cumartesi
  ilk iş test edilecek.
- **Ücretsiz katman notu:** Google, ücretsiz katmanda gönderilen veriyi ürün geliştirmede kullanabiliyor. Test
  sesleri açık veri setlerinden geldiği için sorun değil. Gerçek kişilerle kullanılırsa ücretli key'e geçilmeli.

### K6. Ton kontrolü: LLM sadece tanıtımda, her turda kurallar (2026-11-06)
- **Seçenekler:** Her turda bir LLM'in ton kararı vermesi / sinyalleri doğrudan S2S modele vermek / kurallar.
- **Seçilen:** Kişi profili (CEFR, ilgi alanları) tanıtımda bir kez LLM ile çıkarılıyor. Her turda z-skorlardan
  kurallarla ton parametreleri seçiliyor ve COACH NOTE olarak gönderiliyor.
- **Neden:** Her turda LLM çağırmak cevaba gecikme ekler, ayrıca LLM'in kararları görünmez kalır. Kurallar test
  edilebilir ve literatüre dayanıyor: 250 ms duraksama eşiği, ~%25 yavaşlama, 3 sn bekleme süresi.
- **Hız:** Gemini'de hız parametresi yok, hız doğal dil talimatıyla etkileniyor. Bunun gerçekten işe yarayıp
  yaramadığı M6 ölçümüyle gösterilecek.

### K7. Profil LLM'i: Gemini metin modeli (2026-11-06)
- **Seçenekler:** Claude Haiku / Gemini Flash.
- **Seçilen:** Gemini (aynı ücretsiz key).
- **Neden:** Kişi başına sadece bir kez çağrılıyor, kalite farkı önemsiz. İkinci bir API key gerektirmiyor.

### K8. Prosodi kişinin kendi normaline göre (z-skor); taklit değil uyum (2026-11-06)
- **Neden:** Mutlak değerler kişiden kişiye çok değişiyor. Kişinin konuşma tarzını taklit etmek tuhaf ve alaycı
  durabilir. Aşırı uyumu (patronizing) önlemek için uyum sadece z-eşiği aşılınca yapılıyor.

### K9. Konuşmacı embedding modeli: WeSpeaker ResNet34-LM, `wespeaker` + ONNX (2026-11-06)
- **Seçenekler:** ECAPA-TDNN (SpeechBrain) / WeSpeaker ResNet34 / ResNet293 / CAM++ / pyannote sürümü / eski pyannote embedding.
- **Seçilen:** WeSpeaker ResNet34-LM. Yedek CAM++.
- **Güncelleme (2026-11-06):** Model `sherpa-onnx` ile çalıştırılıyor (aynı ONNX model; fbank çıkarımı kütüphanenin içinde, torch gerekmiyor). 2 sn ses için ~60 ms. Ölçüm: `reports/speaker_id_librispeech.md`.
- **Neden:**
  - VoxCeleb1-O'da EER %0,72; ECAPA'da bu değer %0,87.
  - CPU'da pencere başına onlarca ms.
  - pyannote sürümü Hugging Face token'ı ve ağır kütüphaneler istiyor.
  - ResNet293 demo için gereksiz derecede ağır.

### K10. Temkinli eşik + `unknown` (2026-11-06)
- **Seçilen:** `en_iyi ≥ τ` ve `en_iyi − ikinci ≥ m` şartları sağlanmazsa sonuç `unknown`, Pulsar "Who asked that?" diyor.
- **Neden:** Aynı kişiyi iki kişi saymak daha olası bir hata. Yanlış kişiye ismiyle cevap vermek, "kim sordu?"
  demekten daha kötü bir deneyim.

### K11. ASR: parakeet-mlx, tur sonunda (2026-11-06)
- **Seçenekler:** Whisper (MLX / faster-whisper) / Moonshine / Parakeet.
- **Seçilen:** `parakeet-mlx` + `parakeet-tdt-0.6b-v3`.
- **Neden:**
  - M2'de 37× gerçek zaman hızında çalışıyor.
  - Kelime zaman damgası veriyor; konuşma hızı ve duraksama ölçümleri için gerekli.
  - Whisper'ın M2 ölçümlerini doğrulayamadık.
- **Bilinen açık:** Parakeet'te hotword/prompt desteği yok. "Pulsar" kelimesi transkriptte bulanık eşleşmeyle aranacak.
- **Güncelleme (2026-11-07, ölçümle):** `parakeet-mlx` bf16 yüklüyor: MLX tepe bellek **~2,0 GB** (8 GB'a sığıyor; fp32
  riski kapandı). Diskte model 4,7 GB. AMI turlarında tur başına medyan ~150-200 ms (beklemesiz). Paketin yeni sürümünde
  **kelime güçlendirme** var (`boost.words`, beam search ile) → "Pulsar" için denenecek; bulanık eşleşme yedek kalıyor.
  MLX stream'leri thread'e bağlı: ASR'nin kendi tek thread'i var (`src/pulsar/asr.py`).

### K12. Arayüz: terminal, hazır çerçeve yok (2026-11-06)
- **Seçenekler:** Tarayıcı (WebRTC) / terminal; Pipecat / LiveKit Agents / kendi kodumuz.
- **Seçilen:** Tek Python süreci, `asyncio` + `sounddevice`, terminalde `rich`.
- **Neden:** Kulaklık senaryosunda tarayıcının ek bir faydası yok. Hazır bir çerçeve öğrenmek zaman alır ve tur
  yönetimini gizler; tur yöneticisini kendimiz yazmak projenin asıl öğrenme noktası.

### K13. Veri: AMI Mix-Headset + LibriSpeech; TTS ses yok; gerçek kişi kaydı yok (2026-11-06)
- **Seçenekler:** AMI / Common Voice / LibriSpeech / VoxCeleb / kendi kayıtlarımız / TTS sesleri.
- **Seçilen:**
  - AMI Mix-Headset (test bölümünden 3-4 toplantı): online görüşmedeki karışık sese en yakın kayıt.
  - LibriSpeech test-clean: temiz ses ile karşılaştırma.
- **Neden:**
  - Common Voice artık sadece Mozilla Data Collective hesabıyla indirilebiliyor ve kayıtları kısa okuma cümleleri.
  - TTS sesleri doğruluğu şişirir ve prosodileri yapay. **Smoke testlerde bile TTS kullanılmıyor** (2026-11-06
    güncellemesi); her testte LibriSpeech veya AMI'den gerçek insan sesi var.
  - Gerçek kişi kaydı gerekmiyor, bu da biyometrik veri ve ücretsiz katman sorunlarını ortadan kaldırıyor.

### K14. Geliştirme replay ile, demo canlı Gemini ile (2026-11-06)
- **Neden:** Replay bedava, tekrarlanabilir ve ölçülebilir. Gecikme ve proactive audio davranışı ise ancak canlı
  bağlantıyla ölçülebilir.

### K16. Demoda vektör DB ve RAG yok; ölçeklenmede gelecek (2026-11-06)
- **Seçenekler:** Ses imzalarını ve konuşma geçmişini şimdiden bir vektör DB'de tutmak / bellekte `numpy` ile çalışmak.
- **Seçilen:** Demoda bellekte `numpy`. Uzun süreli hafıza (RAG) ve vektör DB, MIMARI §11'de sonraki adım olarak tasarlandı.
- **Neden:**
  - 3-4 vektör arasında en yakın komşuyu bulmak tek bir matris çarpımı (mikrosaniyeler). Vektör DB'ler milyonlarca
    vektörde hızlı arama için var; burada sadece gereksiz bir katman olurdu.
  - Gemini'ye bir doküman arşivinden bilgi getirmiyoruz; gereken bağlamı doğrudan veriyoruz.
  - RAG, çok oturumlu kullanımda öğrenci başına hafıza için anlam kazanıyor. Arama oturum başında yapılacak,
    her turda değil.
  - Ses imzası araması büyüse bile grup içinde kalmalı (yanlış eşleşme oranı ve gizlilik).

### K17. Gemini 3.8 Live (v1beta) + COACH NOTE turun içinde (2026-11-06, ölçümle)
- **Test:** `reports/gemini_turn_test.md` (gerçek insan sesi, model başına tür başına 3 deneme).
- **Seçilen:** `gemini-3.8-live`, `v1beta`. COACH NOTE aktivite penceresinin içinde gönderiliyor:
  `send_realtime_input(text=…)`, ardından `activity_end`.
- **Neden:**
  - 3.8: 9/9 cevap geldi, isimle hitap 9/9, sesli turda TTFB ~1,6 sn.
  - 2.5 native audio: TTFB 5–7 sn. B yolunda notu 0/3 yok saydı.
  - A yolu iki modelde de çalıştı; B yolu modele göre değişti.
- **Not:** 2.5 sadece `v1alpha`'da bağlanıyor. Yedek olarak kalıyor ama zayıf.

### K18. Demo eşiği: τ=0,45, marj=0,05 (2026-11-07, ölçümle)
- **Seçenekler:** Başlangıç (0,5/0,1) / LibriSpeech ızgarası (0,3/0,05) / AMI ızgarası (0,45/0,05).
- **Seçilen:** AMI ızgarası.
- **Neden:** AMI demo koşullarına en yakın veri: karışık akış ve aynı oturumda kayıt/test. Doğal turlarda (3 kayıtlı + 1
  kayıtsız) sonuç: doğru %88,8, unknown %9,4, yanlış isim %1,9 (< %2 hedefi), kayıtsız kabul %10,1.
  LibriSpeech ayarı AMI'de yanlış isim %2,4 ve kayıtsız kabul %32 verdi, yani eşik veri setleri arasında taşınmıyor.
- **Geçici:** Kayıtsız kişi araştırması (`docs/ARASTIRMA_ISTEGI_kayitsiz_kisi.md`) gelince gözden geçirilecek.

### K19. VAD: `silero-vad` paketi (PyTorch) (2026-11-07)
- **Seçenekler:** `silero-vad` paketi (PyTorch) / sherpa-onnx içindeki Silero VAD / Silero ONNX + kendi döngümüz.
- **Seçilen:** `silero-vad` paketi (6.2.3, torch 2.15).
- **Neden:** Her 32 ms blok için ham konuşma olasılığını doğrudan veriyor. Tur kesme mantığını (500 ms sessizlik vb.)
  kendimiz yazacağız, bu da öğrenmek için en şeffaf yol. Bedeli: `.venv` 795 MB oldu (torch).
- **İlk ölçüm (RTTM'ye karşı, 32 ms bloklar, eşik 0,5):** ES2004a recall %78 / precision %99, EN2002a %84 / %99.
  Eşik 0,2'de recall +4-5 puan. Blok başına 0,18 ms. Kaçırılanlar büyük ihtimalle kısa onaylar ("yeah") ve
  RTTM sınır payları. Başlangıç eşiği 0,5.

### K20. Tur içi konuşmacı değişimi: kayan pencere + aday kesim noktası; < 1 sn'ye isim yok (2026-11-07)
- **Sorun:** VAD konuşmacı değişimini bilmiyor; AMI'de turların ~%28'i karışık, yanlış isimlerin %68'i buradan.
- **Seçenekler:** sessizlik eşiğini kısaltmak (250 ms denendi, çözmedi) / kayan pencerelerle bölmek / hedef konuşmacı
  çıkarma, TS-VAD (üst üste konuşma için; ağır, sonraya).
- **Seçilen:** `segment.py`: 1,5 sn pencere / 0,5 sn kayma, değişim ≥ 2 pencere; kısa boşluklar (≥ 150 ms) aday kesim
  noktası (kullanıcının önerisiyle), sol/sağ ayrı tanınır. Alt turlar kendi sesiyle yeniden tanınır. < 1 sn'ye isim yok.
- **Ölçüm:** konuşma süresine göre doğru %57,5 → %65,7, yanlış %30,3 → %23,5; ama bölünmüş 1-2 sn parçalarda yanlış
  isim %19 (`reports/replay_vad_speaker.md`). `--no-split` ile eski davranış.

### K21. Hitap: greedy ASR + Levenshtein ≤ 1, çoğul hariç; başka katılımcıya hitap kuralı (2026-11-07, ölçümle)
- **Ölçüm** (`reports/addressing_asr.md`, kullanıcının 15 kaydı): ASR "Pulsar"ı 5'te 3 "Pussar" yazıyor.
  Levenshtein ≤ 2 (MIMARI'deki plan) "pulse"u yakalıyor; ≤ 1 isimli 5/5'i yakalıyor, "pulse"u değil.
- **Seçenekler:** lev ≤ 2 / lev ≤ 1 / Parakeet kelime güçlendirme (beam + boost).
- **Seçilen:** greedy + lev ≤ 1; "pulsars" gibi çoğul hali sayılmıyor. Ek kural 0: cümle başka bir katılımcının
  ismiyle başlıyor/bitiyorsa (ve "Pulsar" yoksa) takip penceresi açık olsa bile HAYIR (MIMARI §8 risk 6).
- **Neden boost değil:** ağırlık 2'de soru işaretleri düşüyor (soru kuralı bozulur), ≥ 5'te olmayan yerde "Pulsar"
  duyuyor ("My pulsar was really fast").
- **Test:** 12/12 tek tek + 10/10 senaryo; ama kurallar bu kayıtlara bakılarak ayarlandı, ayrı test seti gerekir.

### K15. İsim ve repo (2026-11-06)
- Asistanın adı **Pulsar**.
- Repo `pulsar-group-voice-coach`, public. "chat" yerine "coach" seçildi, çünkü amaç dil pratiği.
- Repo dokümanları Türkçe başladı. README İngilizce olacak.

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
  - TTS sesleri doğruluğu şişirir ve prosodileri yapay.
  - Gerçek kişi kaydı gerekmiyor, bu da biyometrik veri ve ücretsiz katman sorunlarını ortadan kaldırıyor.

### K14. Geliştirme replay ile, demo canlı Gemini ile (2026-11-06)
- **Neden:** Replay bedava, tekrarlanabilir ve ölçülebilir. Gecikme ve proactive audio davranışı ise ancak canlı
  bağlantıyla ölçülebilir.

### K15. İsim ve repo (2026-11-06)
- Asistanın adı **Pulsar**.
- Repo `pulsar-group-voice-coach`, public. "chat" yerine "coach" seçildi, çünkü amaç dil pratiği.
- Repo dokümanları Türkçe başladı. README İngilizce olacak.

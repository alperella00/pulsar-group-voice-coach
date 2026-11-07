# Pulsar: Teknik Araştırma Raporu (6 Kasım 2026)

**Önerim C modunun hafifletilmiş hâli.** Her konuşma turu yerel VAD ile kesilsin. Kimin konuştuğu speaker embedding ile, ne dediği tur bittikten sonra çalışan yerel ASR ile bulunsun. Basit kurallar Pulsar'a hitap edilip edilmediğine karar versin. Yalnızca Pulsar'a yöneltilen tur, kısa bir metin notuyla birlikte **Gemini 3.8 Live**'a (`gemini-3.8-live`) manuel `activityStart`/`activityEnd` ile gönderilsin. B modu (tüm sesi modele akıtmak) 3 kişilik bir ortamda kimlik ve prozodi bağlamını kaybettiriyor. Ayrıca güvenilirliği hiçbir yerde ölçülmemiş. A modu (wake word) ise Porcupine'in ücretsiz katmanı kapandığı için pahalı bir eğitim işine dönüşüyor.

## TL;DR
- **Mimari:** C-lite. Silero VAD ile tur kesilir. Konuşmacı, WeSpeaker ResNet34-LM embedding'i ve kayıt profiline kosinüs benzerliği ile bulunur. Tur sonunda parakeet-mlx ile ASR yapılır; sürekli streaming ASR gerekmez. Adresleme kural tabanlıdır: isim geçmesi, açık takip penceresi, soru cümlesi. Prozodi parselmouth ile ölçülür. S2S tarafında manuel tur yönetimi kullanılır.
- **Sağlayıcı:** Birincil seçenek Gemini 3.8 Live. Ücretsiz katmanı var. Ücretli tarifede ses girişi dakikada yaklaşık $0.005, çıkışı yaklaşık $0.018. Manuel VAD destekleniyor ve oturum ortasında metin eklenebiliyor. Riski şu: bu modelde proactive audio kalıcı olarak açık ve affective dialog kaldırılmış. Model "cevap vermemeye" karar verebilir, bu ilk gün test edilmeli. Yedekler: `gemini-2.5-flash-native-audio-preview-12-2025` (proactive kapatılabiliyor) ve ücretli `gpt-realtime-2.1-mini` (`speed` parametresi doğrudan var).
- **Gerçekçilik:** "Konuşma bitti → Pulsar konuşuyor < 1.5 s" hedefi sıkı. VAD sessizlik beklemesi (~400 ms), yerel işlem (~150–250 ms) ve S2S'in ilk ses baytı birlikte bütçeyi dolduruyor. Bağımsız ölçümlerde ilk ses baytı 0.6 s ile 1 s'nin üzeri arasında, düşünme seviyesi yüksek modellerde 2–3 s. Hedefi tutmak için düşük düşünme ayarı ve kısa notlar şart. Gecikmeyi JSONL'de ölçüp demoda gösterin.

## Yönetici Özeti

| Karar | Öneri | Kısa gerekçe |
|---|---|---|
| Dinleme modu | **C-lite** | Kimlik, prozodi ve adresleme yerelde kalır. S2S yalnızca gerekli turlarda çağrılır. |
| S2S | **Gemini 3.8 Live** (`gemini-3.8-live`); yedek `gemini-2.5-flash-native-audio-preview-12-2025`; ücretli yedek `gpt-realtime-2.1-mini` | Ücretsiz katman, manuel VAD, oturum ortasında metin ekleme |
| Speaker embedding | `pyannote/wespeaker-voxceleb-resnet34-LM` (alternatif: WeSpeaker CAM++) | VoxCeleb1-O'da EER %0.72. CPU'da pencere başına onlarca ms. |
| VAD | Silero VAD (`silero-vad`) | ~2 MB model; 30+ ms'lik bir chunk tek CPU thread'inde <1 ms'de işleniyor (silero-vad README); 8/16 kHz, MIT lisansı |
| ASR | `parakeet-mlx` + `mlx-community/parakeet-tdt-0.6b-v3`, tur sonunda | Moondream benchmark'ında MacBook Air M2 GPU'da 37× gerçek zaman |
| Prozodi | `praat-parselmouth` (F0, intensity, syllable nuclei); ASR kelime zamanları varsa onlar | Literatürle uyumlu ve hızlı |
| UI | Python süreci + basit terminal veya yerel web panosu (yalnızca gösterim) | Ses I/O için tarayıcı ve WebRTC 3 günde gereksiz karmaşıklık getirir |
| Diarization | Tam diarization yok. Pencereleri en yakın profile atamak yeterli. | 3 kayıtlı kişi, kapalı küme |

**3 günlük yapım sırası (Cmt–Pzt):**
- **Cumartesi sabah:** `uv` projesi, `sounddevice` ile mikrofon girişi ve kulaklık çıkışı, asyncio kuyrukları, JSONL olay kaydı, WAV replay modu (gerçek zamanlı hızda okuma).
- **Cumartesi öğleden sonra:** Gemini 3.8 Live ile "merhaba dünya". Manuel VAD açılır (`automatic_activity_detection.disabled=True`), sabit bir WAV turu gönderilir, ilk ses baytına kadar geçen süre ölçülür. Proactive audio sessiz kalıyor mu, bu sırada test edilir. Sessiz kalıyorsa 2.5 Native Audio modeline geçilir.
- **Pazar sabah:** Silero VAD ile tur kesme. 20–30 s'lik kayıt (enrollment) akışı: 1.5–2 s'lik parçaların embedding'leri alınıp ortalanır. Kosinüs eşiği + marj + "unknown". AMI Mix-Headset üzerinde konuşmacı doğruluğu ölçülür.
- **Pazar öğleden sonra:** parselmouth ile prozodi (F0 medyanı, enerji, konuşma hızı, 250 ms eşikli duraklama, mean length of run). Kayda göre z-skor. Konuşma süresi payları ve proaktif soru kuralı.
- **Pazartesi sabah:** parakeet-mlx ile tur sonu ASR, adresleme kuralları, kısa konuşma özeti, bağlam notu şablonu.
- **Pazartesi öğleden sonra:** Uçtan uca prova. Gecikme kırılımı loglanır. Rıza ekranı ve silme komutu eklenir. README ve demo senaryosu yazılır.


## 0. Dinleme Modu: A / B / C

**Karar: C-lite.** Gerekçeler:
- **B (her şeyi S2S'e akıtmak) zayıf.**
  - Google, Gemini 3.8 Live'da proactive audio'yu "yalnızca kullanıcı hitap ettiğinde ses üretmek, ortam gürültüsünü ve arka plan konuşmasını filtrelemek" diye tanımlıyor.\[1\] Ama çok konuşmacılı bir ortamda güvenilirliğine dair yayımlanmış bir ölçüm bulamadım.
  - Tek karışık akışta model kimin konuştuğunu bilmez. Bizim prozodi notumuzu da tur başına enjekte edemeyiz.
  - Bağlantılar yaklaşık 10 dakikada yenilenmek zorunda.\[2\]
  - Maliyet sorun değil: ses girişi dakikada yaklaşık $0.005, yani bir saatlik akış yaklaşık $0.30.\[3\] Asıl sorun kontrol kaybı.
- **A (wake word) pahalı.**
  - Porcupine'in ücretsiz katmanı 30 Haziran 2026'da kapandı. Picovoice kişisel veya ticari olmayan bir plan da sunmuyor.\[4\]\[5\]
  - openWakeWord'ün resmî Colab eğitim hattı topluluk raporlarına göre bozuk. Topluluk eğiticileri ~20 GB geçici alan ve saatlerce GPU eğitimi istiyor.\[6\]\[7\] Bu, 20 GB diskli bir M2'de 3 gün içinde riskli.
- **C neden uygun:** Konuşmacı kimliği ve prozodi zaten yerelde hesaplanıyor. Adresleme kararına bunlara ek olarak transkript ve zamanlama sinyalleri giriyor. Bu, endüstrinin cihaza yönelik konuşma tespitinde (device-directed speech detection, DDSD) kullandığı sinyal ailesinin aynısı.\[8\]\[9\]
- **"Lite" kısmı:** Sürekli streaming ASR yerine, VAD turu kapattıktan sonra tüm tur tek seferde transkribe edilir. 5 s'lik bir tur, Moondream benchmark'ındaki MacBook Air M2 GPU ölçümüne (37× gerçek zaman) göre ~0.15 s sürer. Bu, streaming kurmanın karmaşıklığını ortadan kaldırır.

## 1. Adresleme (device-directed speech) tespiti

- **Amazon (Mallidi vd., 2018):**
  - Cihaza yönelik sorguyu arka plan konuşmasından ayırıyor. Amaç, sonraki sorgulara wake word gerektirmeyen takip (follow-up) imkânı.\[10\]
  - Model iki LSTM'den oluşuyor: biri akustik özniteliklerde, biri ASR 1-best metninde. İkisinin çıktısı ASR dekoder öznitelikleriyle birleştiriliyor.\[10\]
  - Mallidi vd. (Interspeech 2018) ASR dekoder öznitelikleri, akustik embedding'ler ve 1-best embedding'leri için ayrı ayrı **%9.3, %10.9 ve %20.1 EER**; üçünün birleşimi için %44 göreli iyileşmeyle **%5.2 EER** raporluyor.
- **Apple:**
  - LLM tabanlı DDSD çalışmalarında önceki sorgu ile takip sorgusunun ASR transkriptleri birlikte LLM'e veriliyor.\[11\]\[12\]
  - Multimodal sürüm akustik özellikleri, dekoder sinyallerini ve 1-best hipotezi birleştiriyor.\[8\]\[13\]
  - Wagner vd. (Apple, ICASSP 2024), multimodal yaklaşımın EER'i yalnızca metin ve yalnızca ses modellerine göre göreli olarak sırasıyla %39'a ve %61'e kadar iyileştirdiğini bildiriyor. Bir atıf, 1.5B parametreli GPT-2 ile alınmış **%6.5 EER** sonucunu aktarıyor.
- **Microsoft (Tsai vd.):** Tsai, Stolcke & Slaney (IEEE Trans. Multimedia, 2015), çok taraflı insan-insan-bilgisayar diyaloğunda enerji tabanlı akustik özniteliklerin açık ara en önemli sinyal olduğunu bulmuş. Yine de "akustik + sözcüksel + sistem durumu" kombinasyonu en ekonomik çözüm olarak öneriliyor.
- **Önceki etkileşim bağlamı:** Rudovic vd. (Apple, NeurIPS 2024 workshop), önceki sorgu bağlamını kullanmanın, takip sorgularını tek başına modellemeye kıyasla %10 sabit yanlış ret oranında yanlış alarmları %20–40 azalttığını bildiriyor.
- **Pulsar için hafif kural seti** (öneri; sıra önemli):
  1. Transkriptte "Pulsar" veya ses olarak benzer bir varyant geçiyorsa (bulanık eşleşme) → **hitap var**.
  2. Pulsar'ın son konuşmasından sonraki **8 s** içinde, Pulsar'ın soru yönelttiği kişi konuşuyorsa → **hitap var** (kişiye özel takip penceresi).
  3. Tur soru ile bitiyor ("?" veya wh-/aux ile başlıyor) **ve** son 30 s'de Pulsar'a hitap edilmişse → **hitap var**.
  4. Aksi halde yalnızca kaydet ve konuşma sürelerini güncelle.
  - İsim geçmesi en güçlü sinyal. Yanlış pozitif maliyeti yüksek, çünkü konuşmayı bölmek kötü bir deneyim. Bu yüzden belirsiz durumda sessiz kalın.

## 2. Modelin kendisinin konuşmaya karar vermesi (B)

- **Gemini:**
  - Proactive audio açıkken "içerik ilgisizse Gemini yanıt vermemeye proaktif olarak karar verebilir."\[14\]
  - Davranış modele göre değişiyor:
    - **Gemini 3.8 Live** ve **3.8 Live Extended Thinking:** kalıcı olarak açık; `proactive_audio: false` göndermek hata döndürüyor.\[14\]
    - **Gemini 2.5 Flash Live:** yapılandırılabilir, `v1beta` ile `proactivity={'proactive_audio': True}`.\[14\]
    - **3.1 Flash Live Preview:** desteklemiyor.\[14\]
  - Çok konuşmacılı güvenilirliğine dair bağımsız bir ölçüm bulamadım (**doğrulanamadı**).
- **OpenAI:** Belgelerde Gemini'deki proactive audio'nun bir eşdeğeri yok. Server VAD veya `semantic_vad` her algılanan turda yanıt üretir (`create_response`).\[15\]\[16\]
- **Sürekli akış maliyeti:**
  - Gemini 3.8 Live: ses girişi $3/M token (~$0.005/dk), çıkışı $12/M (~$0.018/dk).\[3\]
  - gpt-realtime-2.1: ses girişi $32/M (~$0.019/dk dinlenen), çıkışı $64/M (~$0.077/dk konuşulan).\[17\]
  - Mini model: $10/$20 per M.\[18\]
  - Gemini'de her tur aktif bağlam penceresi üzerinden faturalanıyor. Biriken ses token'ları sonraki turları pahalılaştırıyor.\[19\]
- **Süre sınırları (Gemini):**
  - Sıkıştırma olmadan yalnızca ses içeren oturumlar 15 dakika, ses+video oturumları 2 dakika.\[2\]
  - Bağlantı ömrü yaklaşık 10 dakika. Kapanmadan önce `GoAway` mesajı (ve `timeLeft`) gelir.\[2\]\[20\]
  - Resumption token'ları oturum sona erdikten sonra 2 saat geçerli.\[21\]\[22\]

## 3. Yerel ASR (C için)

- **parakeet-mlx** (`uv add parakeet-mlx`, varsayılan model `mlx-community/parakeet-tdt-0.6b-v3`):
  - Moondream'in benchmark'ında MacBook Air M2 (10 çekirdekli GPU, 16 GB RAM) üzerinde parakeet-mlx fp32 ile GPU'da **37× gerçek zaman** ölçülmüş. fp32 ağırlıklar 2.51 GB tutuyor, yani aşağıdaki RAM tahminini buna göre yukarı çekin.
  - Streaming API'si var: `model.transcribe_stream(context_size=(256, 256))`.\[23\]
  - Önerim: streaming yerine tur sonunda `model.transcribe()` kullanmak.
  - RAM tahmini: 0.6B parametre ve fp16 ile ~1.2–2 GB (**benim tahminim, ölçülmedi**). 8 GB'a sığar, ama tarayıcı açıkken dikkatli olun.
- **Alternatifler:**
  - Parakeet Realtime EOU 120M: 80–160 ms gecikmeyle akış yapıyor ve konuşma sonunu işaretliyor, ama noktalama yok.\[24\]
  - Moonshine ve küçük Whisper modelleri CPU'da uygulamanın yanında çalışabiliyor (sherpa-onnx ile).\[25\]
  - Whisper small/turbo için M2 RTF ve RAM değerlerini bu araştırmada **doğrulayamadım**.
- **CPU yeterli mi?** Silero VAD ve embedding (ResNet34 ONNX CPU'da pencere başına ~46 ms) CPU'da rahat çalışır.\[26\] ASR'yi MLX ile GPU'ya verin. Hepsi aynı anda sürekli çalışmadığı için (ASR yalnızca tur sonunda) yük tepe noktalarında bile yönetilebilir.
- **"Pulsar" kelimesi:**
  - Parakeet TDT'de Whisper'daki `initial_prompt` gibi bir prompt veya hotword mekanizması yok.
  - Pratik çözüm: transkriptte bulanık eşleşme (`pulsar|pulser|pulse are|pal sir|polsar`, Levenshtein ≤2) ve kayıt sırasında herkesin "Hey Pulsar" demesini isteyip ASR çıktılarını toplayarak varyant listesi çıkarmak.
  - Gemini'nin kendi giriş transkripsiyonu `input_audio_transcription.custom_vocabulary` ile biaslanabiliyor (en fazla 1.000 terim, en iyi sonuç ≤100).\[14\] Ama C'de adresleme kararı S2S'e gitmeden önce verildiği için bu sadece yardımcı olur.

## 4. Spekülatif gönderim ve geri alma

- **OpenAI:**
  - VAD kapalıyken (`turn_detection: null`) ses `input_audio_buffer.append` ile tampona eklenir. Tur `input_audio_buffer.commit` + `response.create` ile tetiklenir.\[16\]\[27\]
  - Commit edilmemiş tampon `input_audio_buffer.clear` ile, commit edilmiş bir öğe `conversation.item.delete` ile silinebilir. Bu olay adları uzun süredir API'de var, ama 2.1 belgelerinde ayrıca **teyit edemedim**.
  - Dolayısıyla spekülatif append + clear mümkün.
- **Gemini:** `activityStart` ile `activityEnd` arasındaki ses bir tur oluşturuyor. Bir turu geri çekmeye yarayan bir mesaj belgelenmemiş. `send_client_content(turn_complete=True)` ise "üretimi koşulsuz keser".\[14\]
- **Öneri: spekülasyon yapmayın.**
  - Turu yerel bir ring buffer'da tutun. Karar verilince hepsini tek seferde gönderin.
  - 5 s'lik 16 kHz PCM16 ses ~160 KB tutar, ağdan onlarca milisaniyede gider.
  - Böylece "yanlışlıkla gönderilen tur modelin bağlamında kalır" riskini tamamen ortadan kaldırırsınız.

## 5. A modu: openWakeWord ve Porcupine

- **openWakeWord:**
  - Hedef: hazır modellerde <%5 yanlış ret ve saatte <0.5 yanlış kabul.\[28\] Eğitim hattı bu hedeflere göre checkpoint seçiyor (recall ≥0.5, FP ≤0.5/saat).\[29\]\[30\]\[31\]
  - Topluluk eğiticileri (Kokoro veya Piper ile sentetik pozitifler) GPU'da 4–8 saat eğitim bildiriyor. Tipik sonuç: "%70+ doğruluk, saatte <2 yanlış pozitif."\[7\]
  - LiveKit wakeword (Apache 2.0, Nisan 2026) openWakeWord formatında ONNX üretiyor. Kendi benchmark'ında saatte 0.08 yanlış kabul ölçmüş; openWakeWord için aynı benchmark'ta 8.50 (**üretici ölçümü**).\[28\]\[32\]
- **Porcupine:** Ücretsiz katman 30 Haziran 2026'da kapandı, yerine 7 günlük deneme geldi. Kişisel veya ticari olmayan bir plan yok.\[5\]\[33\] **Pulsar için uygun değil.**

---

## A. S2S Sağlayıcıları

### 6. Gemini Live API

- **Güncel modeller:**
  - `gemini-3.8-live` ve `gemini-3.8-live-extended-thinking`, 15 Eylül 2026'da yayımlandı, free tier dahil.\[3\]
  - `gemini-3.1-flash-live-preview`.
  - `gemini-2.5-flash-native-audio-preview-12-2025`.
- **Manuel VAD:**
  - Kurulum: `realtime_input_config={"automatic_activity_detection": {"disabled": True}}`.\[14\]
  - Akış: `send_realtime_input(activity_start=types.ActivityStart())`, ses blob'ları (`audio/pcm;rate=16000`), ardından `send_realtime_input(activity_end=types.ActivityEnd())`. Dört modelin hepsinde destekleniyor.\[14\]\[34\]
  - Not: Manuel modda sunucunun kendi ses tamponlama mekanizmaları devre dışı kalıyor.\[14\]
- **Ses akarken metin ekleme:**
  - 3.8 ve 3.1'de `send_client_content` oturum boyunca `user` veya `model` rolleriyle kullanılabiliyor.\[14\]
  - `turn_complete=True` üretimi koşulsuz kesiyor.\[14\] Yani bağlam notunu **`turn_complete=False`** ile gönderin. Ya da notu `send_realtime_input(text=...)` ile aktivite penceresinin içinde, `activity_end`'den önce gönderin.
  - İki yolun sıralama garantisini doğrulayamadım. Cumartesi günü ikisini de deneyin.
- **Yalnızca metinden sesli yanıt:** Evet. `send_client_content(turns=..., turn_complete=True)` ile metin gönderilip `response_modalities=["AUDIO"]` ile ses alınabiliyor. Belgelerdeki örnek tam olarak bu.\[14\] Proaktif "sessiz kişiye soru" özelliği için ideal: sesi olmayan bir metin talimatı yeter.
- **Ücretsiz katman:**
  - Fiyatlandırma sayfası bu model grubu için ücretsiz giriş ve çıkış gösteriyor.\[19\]
  - Ancak dakika, oturum ve eşzamanlılık limitlerini içeren bir tablo yayımlanmamış (**doğrulanamadı**).\[35\]
  - Ücretsiz katmanda gönderilen veriler Google tarafından ürün geliştirmede kullanılabiliyor ve insan incelemesine açık.\[36\] Bu, hukuk bölümü için önemli.
- **Bağlam:** Native audio modellerinde 128k token (3.8 sayfasında 131.072 giriş / 65.536 çıkış).\[19\]
- **Uzun oturumlar:**
  - Sıkıştırma: `context_window_compression={"sliding_window": {}, "trigger_tokens": ...}`.\[2\]\[37\]
  - Kesinti sonrası devam: `session_resumption={}`. `SessionResumptionUpdate.new_handle` saklanır, `GoAway` gelince yeniden bağlanılır.\[2\]\[38\]
  - Konfigürasyon bağlantı açıkken değiştirilemiyor. Model dışındaki parametreler resumption ile yeniden bağlanırken değiştirilebiliyor.\[39\]

### 7. OpenAI Realtime API

- **Modeller:**
  - `gpt-realtime-2.1`: ses $32/$0.40 (cached)/$64 per M, metin $4/$24.\[40\]
  - `gpt-realtime-2.1-mini`: ses $10/$0.30/$20, metin $0.60/$2.40.\[40\]
  - **GPT-Live 1**: 10 Eylül 2026'dan beri GA, dakikası $0.05 + arka uç model ücreti.\[17\]
  - Orijinal `gpt-realtime` 20 Ocak 2027'de kapanıyor.\[17\]
- **Manuel tur:** `session.update` ile `audio.input.turn_detection: null`, ardından `input_audio_buffer.commit` ve `response.create`.\[27\]
- **Tur başına talimat:**
  - `response.create.response.instructions` var.\[41\]
  - `conversation: "none"` ile bant dışı (out-of-band) yanıt da üretilebiliyor.\[42\]
  - Bu, prozodi notunu her yanıt için ayrı vermenin en temiz yolu.
  - Gemini'de bunun doğrudan karşılığı yok. En yakın yol, turun içine metin parçası eklemek. Sistem talimatı ise bağlantı açıkken değiştirilemiyor.
- **Konuşma hızı parametresi:** Var. `speed` 0.25–1.5 arası (varsayılan 1.0) ve "yalnızca model turları arasında değiştirilebilir".\[15\] Gemini'de eşdeğeri yok; hız yalnızca doğal dil talimatıyla etkilenebiliyor.
- **Ücretsiz katman:** OpenAI Realtime için bir ücretsiz katman bulamadım (**doğrulanamadı**). 3 günlük test için mini modelle birkaç dolar yeter.

### 8. Gecikme (konuşma bitti → ilk ses baytı)

- **Artificial Analysis S2S Index (bağımsız):** İlk sese kadar geçen süre (TTFA) GPT-Realtime-1.5'te 0.82 s, GPT-Realtime-2 (High) için 2.33 s, Gemini 3.1 Flash Live Preview (High) için 2.98 s. GPT-Realtime-2 minimal reasoning ile 1.12 s.\[43\]\[44\]
- **Step-Audio-R1 raporu (Big Bench Audio):** Gemini 2.5 Flash Native Audio Dialog 0.63 s, GPT Realtime 0825 0.98 s.\[45\]
- **Google, Gemini 3.8 Live için bir gecikme rakamı vermiyor.**\[44\] Üçüncü taraf bir haber sitesi 180–220 ms iddiasını aktarıyor, ama test düzeneğine özgü ve doğrulanamaz.\[46\] **Güvenmeyin, kendiniz ölçün.**
- **Sonuç:** Düşük düşünme ayarı + kısa bağlam notu + yerel karar ≤250 ms ile 1.5 s hedefi mümkün, ama garanti değil.

### 9. Ton kontrolü ve affective dialog

- **Affective dialog:** "Gemini'nin yanıt stilini girdinin ifadesine ve tonuna uyarlamasını" sağlıyor.\[14\]
  - Yalnızca Gemini 2.5 Flash Live'da var. 3.8'de kaldırılmış, 3.1'de yok.\[14\]
  - Bir Google Cloud sayfası 3.8'de varsayılan açık olduğunu yazıyor.\[1\] Bu, AI Studio belgeleriyle **çelişiyor**. Güncel olan AI Studio capabilities sayfasını esas alın.
- **Bizim yaklaşımımızla farkı:**
  - Affective dialog örtük ve kara kutu. Kimin "her zamankinden" yavaş olduğunu bilmez, çünkü kişisel bir referansı yok.
  - Bizim z-skor yaklaşımımız açık, kişiye göre ve loglanabilir.
- **Talimata uyum:** "Yavaş konuş, sıcak ol" gibi doğal dil talimatlarına sesli çıktıda ne kadar uyulduğunu ölçen bağımsız bir çalışma bulamadım (**doğrulanamadı**).
  - Pratikte cümle uzunluğu ve kelime seviyesi metin talimatıyla iyi kontrol edilir, çünkü bunlar içerik.
  - Hız ve sıcaklık daha değişkendir.
  - Hız gerçekten kritikse OpenAI'ın `speed` parametresi deterministik tek araç.

### 10. Konuşmacıyı modele bildirmek

- Tek oturumda en sağlam yol, her turda kısa bir metin etiketi göndermek. Sistem talimatı Gemini'de bağlantı açıkken değiştirilemiyor.
- Önerilen format (İngilizce, kısa):
  `[COACH NOTE] Speaker: Ayşe (B1). Now: slower than her baseline (z=-1.4), many pauses (z=+1.8). Reply to Ayşe by name. ≤2 short sentences, simple B1 words, slow, warm, end with an easy question.`
- Sistem talimatına sabit kuralları yazın: "Only the COACH NOTE tells you who spoke; never guess speakers from voice."
- OpenAI'da aynı not `response.create.response.instructions` içine konur.

### 11. Amazon Nova 2 Sonic ve Hume EVI

- **Nova 2 Sonic** (`amazon.nova-2-sonic-v1:0`, Bedrock `InvokeModelWithBidirectionalStream`):
  - Cross-modal metin girişi var (`"interactive": true`).\[47\]
  - Turn-taking duyarlılığı (`endpointingSensitivity`) ayarlanabiliyor,\[47\] ama tamamen manuel tur modu belgelerde **bulamadım**.
  - "Girdinin prozodisine göre adaptif yanıt" sunuyor.\[48\]
  - Bağlantı sınırı 8 dakika. Bağlam 1M token.\[49\]\[50\]
  - AWS hesabı ve ücret gerekiyor. 3 günlük demo için gereksiz bir risk.
- **Hume EVI:**
  - Oturum ortasında `session_settings` mesajıyla sistem prompt'u ve değişkenler güncellenebiliyor. `user_input` ile metin eklenebiliyor.\[51\]\[52\]
  - Prozodi modeli kullanıcının sesindeki "tune, rhythm, timbre" ölçümlerini akış halinde veriyor ve mesajlara `models.prosody.scores` olarak duygu ifadesi skorları ekliyor (ör. Admiration, Adoration).\[53\]\[54\]
  - Hume'un kendi SSS'i bu skorların bir gözlemcinin ifadeyi nasıl yorumlayacağına dair bir tahmin olduğunu, kişinin gerçek duygusunu göstermediğini belirtiyor.\[55\]
  - Turn detection Config içinde ayarlanıyor;\[52\] tamamen manuel tur ve proaktif konuşma desteğini **doğrulayamadım**.
  - Pulsar'ın kişisel referanslı z-skorları Hume'un genel duygu skorlarından farklı bir şey ölçüyor: akıcılık. Hume rakip değil, bir referans.

---

## B. Konuşmacı Tanıma

### 12. Model karşılaştırması

| Model | VoxCeleb1-O EER | Not |
|---|---|---|
| WeSpeaker ResNet34 (LM) | %0.723 | pyannote sarmalayıcısı: `pyannote/wespeaker-voxceleb-resnet34-LM`, 256 boyut |
| WeSpeaker ResNet293 | %0.447 | Çok daha ağır; demo için gereksiz |
| ECAPA-TDNN (SpeechBrain, C=1024) | %0.87 | 14.7M parametre |
| CAM++ | %0.787 (yerel ONNX ölçümü) | 7.2M parametre; ResNet34 ve ECAPA'dan 2 kat hızlı çıkarım |
| ReDimNet2+ | %0.35 | En yeni ve en iyi; kurulum olgunluğu belirsiz |
| pyannote/embedding (eski SincNet x-vector) | %2.8 | Kullanmayın |

- **Kısa test sesi:**
  - 1 s'lik segmentlerde başarım çöküyor. Bir 2026 çalışmasında ECAPA tabanının 1 s'de EER'i **%18.4**.\[56\] 2–3 s'de durum çok daha iyi.
  - Gerçek toplantı verisinde bir değerlendirme: 19 çağrı, 16 kişi, 1.5–6 s pencereler. ResNet34-LM tek pencerede ~%25 EER, PLDA ile %9.1 EER. Ses başına sıralama-1 doğruluğu 46'da 34. CPU'da ONNX ile pencere başına 46 ms.\[26\]
  - Yani VoxCeleb rakamları gerçek mikrofon ve sıkıştırma koşullarında çok iyimser kalıyor.
- **Apple Silicon hızı:**
  - ResNet34-LM CoreML'de batch 1 için yalnızca CPU ile 26.4 ms, tüm hızlandırıcılarla 7.3 ms.\[26\]
  - diart pipeline'ında CPU'da 150 ms (5 s chunk).\[57\]
- **Öneri:**
  - Varsayılan model `pyannote/wespeaker-voxceleb-resnet34-LM`. HF koşullarını kabul edip token gerekir. Alternatif olarak `wespeaker` paketi ve ONNX.
  - Kapalı 3 kişilik küme ve ≥1.5 s turlar için yeterli.
  - CAM++ bir hız alternatifi; zaman kalırsa A/B testi yapın.

### 13. Kayıt (enrollment) süresi

- Doğrudan 10/20/30 s karşılaştırması yapan bir kaynak bu araştırmada **bulunamadı**.
- Pratik öneri: 20–30 s'lik tanıtımı 2 s'lik, %50 örtüşen parçalara bölün. Her parçanın embedding'ini L2-normalize edip ortalayın, sonra tekrar normalize edin.
  - Bu, test koşuluna (kısa turlar) benzeyen parçalardan bir merkez (centroid) üretir.
  - Ayrıca parçalar arası benzerlik dağılımı kişi bazlı eşik kalibrasyonu için hazır veri sağlar: kişinin kendi parçaları arasındaki benzerliğin 5. yüzdeliği.
- Tek embedding mi, ortalama mı sorusunu AMI üzerinde 10/20/30 s ile kendiniz ölçün.

### 14. Eşik ve marj kalibrasyonu

- Kapalı küme (3–4 kişi) için karar kuralı:
  `best ≥ τ` **ve** `best − second ≥ m` → kişi; aksi halde `unknown`.
- Başlangıç değerleri: ResNet34 kosinüs için τ≈0.45–0.55, m≈0.08–0.12 (**deneyim tabanlı başlangıç, kaynakla doğrulanmadı**). Değerleri AMI Mix-Headset'te turlar üzerinde grid search ile seçin. Hedef: yanlış isimle hitabı <%2'de tutarken unknown oranını en aza indirmek.
- AS-norm: WeSpeaker'ın raporladığı sonuçlar cosine + AS-norm ile alınmış.\[58\] Ama 3 kişilik kapalı kümede marj kuralı zaten göreli normalizasyon işlevi görüyor. Demo için **gerekmez**.
- Kısa turlarda kararı yumuşatmak için konuşmacı değişmediyse önceki turun etiketine küçük bir öncül (prior) ekleyin.

### 15. Online diarization

- **diart:** pyannote segmentation ve embedding ile CPU'da gerçek zamanlı çalışıyor; gecikmesi 500 ms–5 s arası ayarlanabiliyor. Bir 2026 karşılaştırmasında VoxConverse'te en iyi ikinci streaming sistem (%16.12 DER).\[59\]\[60\]
- **Streaming Sortformer:**
  - En fazla 4 konuşmacı önbelleğiyle çalışıyor, 3 kişi için uygun.\[61\]
  - Bir karşılaştırma PyTorch sürümünün GPU istediğini söylüyor. CoreML portu ise Neural Engine'de 480 ms'lik adım başına 8.1 ms'de çalışıyor ve küçük bir pilotta %8.1 DER veriyor.\[61\]\[62\]
  - Python'dan kullanımı zahmetli; çoğu Swift.
- **Toplantı DER'i bağlamı:** pyannote 3.1 offline'da AMI headset-mix'te %18.8 DER veriyor.\[63\] Streaming'in offline'a göre %10–15 daha kötü olması bekleniyor.\[60\]
- **Konuşma süresi payı hatası** doğrudan raporlanmıyor. DER'in "confusion" bileşeni (AMI'de ~%5.7) iyi bir vekil.\[63\]
- **Örtüşen konuşma tespiti:** Kulaklıklı online görüşmelerde örtüşme az ve kısa. Demo için **değmez**. Örtüşen pencereleri "overlap" olarak işaretleyip konuşma süresi payına katmayın.
- **Sonuç:** Kayıtlı profillerle "her VAD turunu, gerekirse 1.5 s'lik alt pencereleri, en yakın profile ata" yaklaşımı yeterli. Tam diarization gereksiz.

---

## C. Prozodi ve Pedagoji

### 16. Pitch çıkarımı

- **Öneri: `praat-parselmouth`.** `snd.to_pitch_ac(pitch_floor=75, pitch_ceiling=500)`, kadın ve erkek için kişiye göre floor/ceiling, kayıt verisinden çıkarılmış.
  - Hızlı ve konuşma için standart.
  - Hece çekirdeği tespiti aynı araçla yapılabiliyor.
- **Alternatifler:** librosa `pyin` daha yavaş ama olasılıksal voicing veriyor. CREPE, PESTO ve RMVPE sinir ağı tabanlı ve gürültüde genelde daha sağlam.
- **Bu araştırmada sıkıştırılmış toplantı sesinde bu dört aracı karşılaştıran bir benchmark'ı ve M2 hız ölçümlerini doğrulayamadım.**
- Pratik not: z-skor için mutlak doğruluktan çok tutarlılık önemli. Medyan F0 ve F0 aralığı (10.–90. yüzdelik) kullanın. Tek kare hataları medyanla bastırılır.

### 17. ASR'siz konuşma hızı (de Jong & Wempe)

- de Jong & Wempe (2009, *Behavior Research Methods* 41(2)) Praat script'i:
  - Elle sayılan konuşma hızıyla **r = .71** (≥5 s'lik konuşma parçaları başına) ve **r = .88** (dosya veya görev başına) korelasyon veriyor.\[64\]
  - Vurgusuz heceleri kaçırdığı için hızı sistematik olarak düşük tahmin ediyor. Elle sayılan hızı tahmin etmek için ~1.28–1.29 katsayısıyla çarpılmalı.\[64\]\[65\]
- **Sonuç:** Kısa turlarda (2–5 s) güvenilirlik düşer.
  - ASR kelime zaman damgaları varsa (parakeet-mlx timestamp veriyor), heceyi sözlükten veya `pyphen` ile sayıp zamanla bölmek daha iyi.
  - Syllable-nuclei yöntemini yedek ve tutarlılık kontrolü olarak tutun.
  - Her iki durumda da z-skor kişinin kendi referansına göre hesaplandığı için sistematik sapma büyük ölçüde iptal olur.

### 18. L2 akıcılık ölçütleri

- **Duraklama eşiği:** de Jong & Bosker (2013, DiSS) 250–300 ms eşiklerin yeterlik ve akıcılıkla en yüksek korelasyonu verdiğini buldu. Sonuçları: "geleneksel 250 ms kesim noktası iyi bir seçim."\[66\]\[67\] **Pulsar: 250 ms.**
- **Algılanan akıcılıkla ilişki:** Suzuki, Kormos & Uchihara (2021, *Modern Language Journal*) meta-analizi, 22 çalışma.\[68\]
  - Bileşik ölçüler (speech rate, mean length of run): **r ≈ .72–.76**\[68\]
  - Hız ve duraklama sıklığı: **r ≈ .59–.62**\[68\]
  - Duraklama süresi: **r ≈ .46**\[68\]
  - Onarım (repair): **r ≈ .20**\[68\]
  - Otomatik anotasyonda korelasyonlar biraz daha düşük.\[69\]
- **Kormos & Dénes (2004, *System*):**
  - En iyi yordayıcılar konuşma hızı, mean length of run ve pace. Birlikte akıcılık puanlarının varyansının %60–80'ini açıklıyor.\[70\]
  - Articulation rate ve dakika başına duraklama sayısı akıcılık puanlarıyla ilişkili çıkmamış.\[70\]
  - Alt-orta seviye grup değerleri: konuşma hızı ~115.9 hece/dk (~1.93 hece/s), MLR ~3.49 hece, ortalama duraklama ~959 ms.\[70\]
- **Tavakoli vd. (2020, *MLJ*; CEFR A2–C1):**
  - Hız ve bileşik ölçüler A2/B1/B2'yi ayırıyor. A2 konuşmacılarının sessiz duraklamaları belirgin biçimde uzun.\[71\]
  - **Cümle ortası (mid-clause) duraklama sıklığı** alt seviyeyi (A2/B1) üst seviyeden ayırıyor.\[71\]\[72\]
- **Ana dil karşılaştırması (Baese-Berk & Morrill, 2015):** Okuma hızı L1 İngilizcede 4.92 hece/s, L1 Korecede 3.95, L1 Mandarincede 4.08.\[73\]
- **Pulsar için "zorlanıyor" sinyali** (öneri, kişisel z-skor ile): konuşma hızı z ≤ −1, **ve** MLR z ≤ −1 veya mid-clause duraklama sıklığı z ≥ +1, **ve** ortalama duraklama >~900 ms. İkisi tutarsa "zorlanıyor" notu, biri tutarsa "biraz yavaş" notu.

### 19. Öğretmen konuşması ve uyum: somut kurallar

- **Bekleme süresi (wait time):**
  - Rowe (1986, *Journal of Teacher Education*): öğretmenlerin tipik bekleme süresi <1 s.\[74\]
  - Soru sonrası beklemenin ve özellikle öğrenci cevabından sonraki beklemenin ≥3 s'ye çıkarılması öğrenci dilinde, mantığında ve tutumlarında belirgin değişiklikler getiriyor. Etkinin başladığı eşik ~2.7 s.\[75\]\[76\]
  - İkinci dil sınıflarında öğrenci cevabından sonraki bekleme süresi 0.73 s ölçülmüş (Shrum 1985, Rowe'dan aktarma; **ikincil kaynak**).\[75\]
  - **Pulsar kuralı:**
    - Soru sorduktan sonra en az 3 s bekle.
    - Konuşmacının duraklaması 250 ms–2 s arasındaysa tur sonu sayma. Zorlanan kişide VAD tur sonu sessizliğini 700–900 ms'ye çıkar.
    - Proaktif soru kuralındaki "≥3 s sessizlik" literatürle uyumlu.
- **Konuşma hızı:**
  - Anderson-Hsieh & Koehler (1988) deneyindeki hızlar: yavaş 2.39–2.65 hece/s, normal 3.25–3.49, hızlı 4.22–4.58. Yavaş, normalden ~%25 düşük.\[77\]
  - Yabancıya yönelik konuşmada (foreigner-directed speech) daha yavaş konuşma, uzun vurgulu ünlüler ve genişlemiş ünlü alanı görülüyor (Scarborough vd.).\[78\]
  - Derwing & Munro (2001): bilgisayarla yavaşlatılmış konuşma tercih edilmedi.\[79\]
  - **Kural:** Zorlanan kişiye "about 25% slower than normal, natural pauses between sentences" talimatı verilsin. Yapay aşırı yavaşlatma yok. OpenAI kullanılıyorsa `speed≈0.8`.
- **Cümle uzunluğu ve kelime dağarcığı (öneri, literatürden türetilmiş tasarım kararı):**
  - A2: ≤8 kelime, en sık 1–2 bin kelime.
  - B1: ≤12 kelime.
  - B2+: doğal.
  - Her yanıtta en fazla 2 cümle ve 1 kolay soru.
  - Zorlanan kişiye önce kısa bir onay ("Good point, Ayşe."), sonra bir soru.
- **Uyum teorisi (accommodation):** Aşırı uyum (patronizing) riskine karşı yalnızca z-skor eşiği aşıldığında uyum yapın. Kişi kendi referansına döndüğünde normale dönün.

---

## D. Ses Altyapısı

### 20. Mimari

- **Önerim: tek Python süreci, `asyncio` + `sounddevice`.**
  - `sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=512, callback=...)`. Callback ayrı bir thread'de çalışır. İçinde yalnızca `loop.call_soon_threadsafe(q.put_nowait, bytes)` çağrılır.
  - `sd.OutputStream(samplerate=24000, ...)`. Gemini çıkışı 24 kHz PCM16.\[14\] Callback bir oynatma ring buffer'ından okur. `server_content.interrupted` veya yeni bir tur gelince buffer temizlenir.\[14\]
  - Asyncio görevleri:
    - `vad_task`: 32 ms kareler, tur kesme
    - `turn_worker`: embedding, prozodi, ASR, adresleme. Ağır işler `asyncio.to_thread` ile.
    - `s2s_sender` ve `s2s_receiver`: WebSocket tarafı
    - `talktime_monitor`: proaktif soru zamanlayıcısı
    - `jsonl_logger`
  - Replay modu: `InputStream` yerine WAV'ı 32 ms'lik bloklar halinde `asyncio.sleep(0.032)` ile besleyen bir üretici. Kodun geri kalanı değişmez.
- **Tarayıcı (getUserMedia/WebRTC):** Tek bir dizüstü ve kulaklık senaryosunda ek fayda sağlamıyor; WebSocket ve kodlama katmanı ekliyor. **Kullanmayın.** Görsellik isteniyorsa konuşma süresi paylarını ve son olayları gösteren salt okunur bir yerel web panosu (SSE) yeterli.
- **Çerçeveler:**
  - LiveKit Agents'ın Gemini eklentisi otomatik aktivite tespitini kapatıp kendi tur tespitçisini kullanmayı destekliyor.\[80\]
  - Pipecat ve FastRTC'nin özel tur yöneticisi desteğini bu araştırmada **doğrulayamadım**.
  - 3 günlük bir projede öğrenme maliyeti yüzünden **kullanmamanızı** öneririm. Tur yöneticisini kendimiz yazmak, çerçevenin soyutladığı her şeyi görmek demek.

---

## E. Hukuk, Etik, Ürün

### 21. UK GDPR ve KVKK (**bu bölüm bu araştırmada birincil kaynakla doğrulanmadı; genel bilgi**)

- **Biyometrik veri:** Kişiyi benzersiz biçimde tanımlamak için işlenen ses embedding'i UK GDPR m.9 kapsamında "özel kategori" biyometrik veri sayılır. Pratikte **açık rıza** gerekir. KVKK m.6'da da biyometrik veri özel nitelikli kişisel veri. Rıza açık, bilgilendirilmiş ve belirli konuya özgü olmalı.
- **Transkripsiyon (C):** Tüm konuşmanın metne dökülmesi kişisel veri işleme demek. Amaç sınırlaması ve veri minimizasyonu gerekir.
- **Ücretsiz Gemini katmanı:** Google'ın ücretsiz katmanda verileri ürün geliştirmede kullanabilmesi ve insan incelemesi, katılımcılara açıkça söylenmeli.\[36\] Gerçek kişisel verilerle ücretli katman tercih edilir.
- **Demo için asgari uyumlu tasarım:**
  1. Başlangıçta rıza ekranı: biyometrik profil + transkript + üçüncü taraf S2S. Her biri ayrı onay kutusu.
  2. Ham ses diske yazılmaz. Embedding'ler yerelde, oturum sonunda silinir (veya `pulsar forget <isim>` komutu).
  3. Transkript yalnızca bellekte, son ~2 dakikalık özet. JSONL'de metin yerine özellikler ve olaylar.
  4. Yalnızca hitap edilen turlar buluta gider.
  5. README'de saklama süresi ve silme talimatı.
  - Gerçek bir ürün için veri koruma etki değerlendirmesi (DPIA) ve hukuk danışmanlığı gerekir.

### 22. Ürünler ve rakipler

- **Birebir AI konuşma koçları** (Lucida, Praktika, Speak, Duolingo'nun sesli özellikleri dahil) bire bir konuşma odaklı.\[81\] Grup konuşması moderasyonu yapan bir ürünü bu araştırmada **doğrulayamadım**. Pulsar'ın farklılaşma noktası bu.
- **Toplantı asistanları** (**bu araştırmada doğrulanmadı, genel bilgi**):
  - Zoom AI Companion ve Google Meet Gemini, katılımcı başına ayrı ses kanalı ve hesap bilgisinden konuşmacıyı bilir.
  - Otter ve Fireflies gibi bot tabanlı araçlar platformun konuşmacı meta verisini kullanır. Tek mikrofonlu oda kayıtlarında ise ses tabanlı diarization ve kullanıcı etiketlemesiyle öğrenilen ses profillerine dayanır.
  - Pulsar'ın tek karışık akışı en zor durumdur. Bu, ses parmak izini gerekçelendirir.

---

## F. Veri Kümeleri

### 23. AMI

- **Kanal: `Mix-Headset`** (tüm kafa mikrofonlarının toplamı). Online görüşmede herkesin kendi mikrofonunun karışmasına en çok benzeyen kanal bu. Örnek: `ES2004a.Mix-Headset.wav`.\[85\]
- **Boyut:** ~30 dakikalık bir toplantı 16 kHz mono PCM16'da ~58 MB eder (16000×2×1800 bayt; **hesap, kaynak değil**).
- **RTTM:** `BUTSpeechFIT/AMI-diarization-setup` deposu (Full-corpus-ASR bölümü, anotasyon v1.6.2; `only_words/rttms/{train,dev,test}`). pyannote eğitiminde de bu kullanılıyor.\[86\]\[87\]
- **En kolay yollar:**
  - Tek dosya: AMI Corpus Mirror'dan `wget` (pyannote eğitim defterinde örnek var).\[85\]
  - Toplu: HF `edinburghcstr/ami` (eski `legacy-datasets/ami` artık önerilmiyor) veya diarization için hazırlanmış `diarizers-community/ami`.\[88\]\[89\]
  - Sınırlı disk için yalnızca test bölümünden 3–4 toplantı indirin.
- **Not:** AMI toplantıları 4 kişilik.\[85\] 3 kişilik test için RTTM'deki bir konuşmacının bölümlerini "unknown" testi olarak kullanın. Bu, kayıtsız kişi senaryosunu da ölçer.

### 24. Common Voice ve alternatifler

- **Erişim:** Ekim 2025'ten beri Common Voice veri kümeleri **yalnızca Mozilla Data Collective (MDC)** üzerinden dağıtılıyor.\[90\]\[91\] HF'deki eski depolar boş.\[92\]
  - Hesap gerekiyor. İndirme tarayıcıdan, MDC API'siyle veya MDC Python SDK'sıyla (pandas DataFrame olarak) yapılabiliyor.\[93\]\[94\]
  - Güncel sürüm: Scripted Speech v27 (Eylül 2026). Eski sürümler e-postayla talep ediliyor.\[93\]\[95\]
- **`client_id`:**
  - Katkıcı başına anonim bir kimlik. Aynı kişinin birden fazla `client_id`'si olabiliyor (**genel bilgi**).
  - Klipler kısa okuma cümleleri, yaklaşık 3–6 s. Toplantı sesine benzemiyor.
  - Kimlik testinde kullanılabilir. Kayıt için kişi başına aynı `client_id`'den 6–10 klibi birleştirin.
- **Alternatifler:**
  - LibriSpeech (OpenSLR, sesli kitap okuması, konuşmacı ID'leri güvenilir).
  - VoxCeleb1 test seti (40 konuşmacı, gerçek dünya kayıtları).
  - Pulsar'ın asıl senaryosu için en gerçekçi test hâlâ AMI Mix-Headset.

---

## G. Benzer projeler (2026-11-07, kullanıcının taraması; kaynaklar henüz doğrulanmadı)
| Proje | Benzerlik | Fark / bize ne lazım |
|---|---|---|
| NVIDIA NeMo Voice Agent + Streaming Sortformer | Her turda konuşmacı kimliği LLM'e gidiyor ("Speaker: Ayşe" fikri) | STT→LLM→TTS zinciri. **Sortformer** kare düzeyinde, örtüşmeyi de gören streaming diarization: bizim karışık tur sorununa (replay ölçümü, yanlış isimlerin %68'i) doğrudan aday. M2/8 GB'da çalışır mı bakılmalı |
| Telnyx Skip Turn | Çok kişili aramada hitap edilmedikçe susuyor | Kararı LLM bir "sırayı geç" aracıyla veriyor; bizde lokal kurallar (K3). Görüşmede karşılaştırma için |
| Adaptis (StartHack25) | Kayıt + ECAPA (192 boyut) + FAISS, kişi başı hafıza | Demo ölçeğinde aynı tasarım. FAISS bizde gereksiz (K16). Kayıt/eşik nasıl yapılmış, kod incelenebilir |
| Dexway | Dil kursunda AI kolaylaştırıcılı grup konuşma | Ürün olarak en yakın; konuşmacı tespiti doğrulanamadı |
| ConversAR (arXiv) | Tek öğrenci + AI ajan grubu | Literatürde grup konuşma pratiği boşluğu: README gerekçesi için alıntı |

## Uyarılar
- Model adları, fiyatlar ve özellikler (Gemini 3.8 Live, gpt-realtime-2.1, GPT-Live 1) Eylül–Ekim 2026 kaynaklarından. Çoğu fiyat rakamı resmî sayfaları aktaran üçüncü taraf sitelerden geliyor. Kodlamadan önce `ai.google.dev` ve `platform.openai.com` fiyat sayfalarını kontrol edin.
- Gemini 3.8'de affective dialog'un durumu konusunda Google'ın iki belgesi çelişiyor.
- Gemini ücretsiz katmanının dakika, oturum ve eşzamanlılık limitleri yayımlanmamış.
- Doğrulanamayanlar:
  - Whisper ve Moonshine M2 ölçümleri
  - pitch araçları karşılaştırması
  - enrollment süresi deneyleri
  - eşik başlangıç değerleri
  - Pipecat ve FastRTC yetenekleri
  - toplantı asistanlarının yöntemleri
  - GDPR ve KVKK ayrıntıları
  - OpenAI `input_audio_buffer.clear` ve `conversation.item.delete` olaylarının güncel belgelerde yer alması
- Bunları ilk gün kısa testlerle doğrulayın ve sonuçları JSONL'e kaydedin.
- Gecikme rakamları ağa ve ölçüm noktasına çok bağlı. Bağımsız ölçümler (0.63–2.98 s) arasında büyük fark var. Kendi ölçümünüz tek güvenilir referans.

## Sources

1. [Developer's guide to Gemini 3.8 Live | Gemini Enterprise Agent Platform | Google Cloud Documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-live)
2. [Session management with Live API | Gemini API | Google AI for Developers](https://ai.google.dev/gemini-api/docs/live-api/session-management)
3. [Gemini 3.8 Live and 3.8 Live Extended Thinking: Google's Audio-to-Audio Voice Models, Benchmarked and Priced](https://www.developersdigest.tech/blog/gemini-3-8-live-extended-thinking-release-guide-2026)
4. [Porcupine Free Tier shutdown: alternatives for Home Assistant voice users? - Third party integrations - Home Assistant Community](https://community.home-assistant.io/t/porcupine-free-tier-shutdown-alternatives-for-home-assistant-voice-users/1012382)
5. [FAQ](https://picovoice.ai/docs/faq/general/)
6. [GitHub - nibor1896/custom-wakeword-trainer: Train your own custom openWakeWord wake-word model locally (Windows / Python 3.13, where the official notebook is bit-rotted). 'Hey Horus' included as the first example model. · GitHub](https://github.com/nibor1896/custom-wakeword-trainer)
7. [GitHub - CoreWorxLab/openwakeword-training · GitHub](https://github.com/CoreWorxLab/openwakeword-training)
8. [Multimodal Data and Resource Efficient Device-Directed Speech Detection with Large Foundation Models](https://arxiv.org/pdf/2312.03632)
9. [MULTIMODAL ADDRESSEE DETECTION IN MULTIPARTY DIALOGUE SYSTEMS TJ Tsai⋆](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/addressee_conf.pdf)
10. [Device-directed Utterance Detection — Speech & Audio](https://awesomepapers.io/speech-audio/papers/1808.02504)
11. [Device-Directed Speech Detection for Follow-up Conversations Using Large Language Models](https://arxiv.org/pdf/2411.00023)
12. [Device-Directed Speech Detection for Follow-up Conversations Using Large Language Models](https://arxiv.org/html/2411.00023v1)
13. [Multimodal Data and Resource Efficient Device-directed Speech Detection with Large Foundation Models](https://arxiv.org/html/2312.03632.pdf)
14. [Live API capabilities guide | Gemini API | Google AI for Developers](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
15. [Realtime server events](https://developers.openai.com/api/reference/resources/realtime/server-events)
16. [Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
17. [OpenAI Realtime API: Production Voice Agents (2026)](https://www.forasoft.com/blog/article/openai-realtime-api-voice-agent-production-guide-2026)
18. [OpenAI Realtime API Pricing 2026: Cost Per Minute Math](https://www.layer3labs.io/guides/openai-realtime-api-pricing)
19. [Gemini 3.8 Live API: IDs, Tools, Limits & Pricing](https://dmarketertayeeb.com/blog/gemini-3-8-live-api-overview/)
20. [Google Live: calls drop around 10 min — no sessionResumption / goAway handling (Gemini 3.8 Live) · Issue #756 · hkjarral/AVA-AI-Voice-Agent-for-Asterisk · GitHub](https://github.com/hkjarral/AVA-AI-Voice-Agent-for-Asterisk/issues/756)
21. [Gemini Live session resumption for mid-turn connection loss and goAway (spike with go/no-go gate) · Issue #18 · adhishthite/tok · GitHub](https://github.com/adhishthite/tok/issues/18)
22. [Gemini 3.8 Live API: Tools, Reasoning, and Session Handling](https://wavespeed.ai/blog/audio-and-voice-models/gemini-3-8-live-api-tools/)
23. [GitHub - senstella/parakeet-mlx: An implementation of the Nvidia's Parakeet models for Apple Silicon using MLX. · GitHub](https://github.com/senstella/parakeet-mlx)
24. [NVIDIA Parakeet Models: V2, V3, Ultra, Redux Compared](https://spokenly.app/blog/parakeet-models)
25. [Best Open Source Speech to Text Models in 2026: 10 Ranked](https://micdrop.dev/blog/top-open-source-speech-to-text-models)
26. [nikioth/wespeaker-resnet34-lm-coreml · Hugging Face](https://huggingface.co/nikioth/wespeaker-resnet34-lm-coreml)
27. [Guide - OpenAI Agents SDK](https://openai.github.io/openai-agents-python/realtime/guide/)
28. [Wake Word Detection in a Web App: openWakeWord vs Porcupine](https://micdrop.dev/blog/wake-word-detection-web-app)
29. [Wake Word Detection: How It Works and How to Train a Custom Wake Word](https://www.speechdata.ai/blog/wake-word-detection)
30. [On-Device Wake-Word Comparison — VoxRT vs Porcupine & openWakeWord](https://voxrt.com/wake-word-comparison)
31. [Model Training](https://deepwiki.com/dscripka/openWakeWord/4.3-model-training)
32. [Outspoken — Custom Wake Word Models](https://outspoken.cloud/blog/best-wake-word-tools)
33. [Picovoice Discointinues Free Tier](https://news.ycombinator.com/item?id=48248969)
34. [Best practices with Gemini Live API | Gemini Enterprise Agent Platform | Google Cloud Documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/best-practices)
35. [Gemini 3.8 Live: 131K Context, 76.0 Voice AI Score (2026)](https://hokai.io/hub/models/gemini-3.8-live)
36. [Google AI Studio](https://en.wikipedia.org/wiki/Google_AI_Studio)
37. [Start and manage live sessions | Gemini Enterprise Agent Platform | Google Cloud Documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/start-manage-session)
38. [Session Management with Googles Multimodal Live API](https://medium.com/google-cloud/session-management-with-googles-multimodal-live-api-f70a162a4374)
39. [Live API - WebSockets API reference | Gemini API | Google AI for Developers](https://ai.google.dev/api/live)
40. [OpenAI API Pricing: A Complete Breakdown for 2026](https://www.g2.com/articles/openai-api-pricing)
41. [Realtime client events](https://developers.openai.com/api/reference/resources/realtime/client-events)
42. [Realtime API Reference](https://www.core42.ai/compass/documentation/realtime-api-reference)
43. [Announcing the Artificial Analysis Speech to Speech Index](https://artificialanalysis.ai/articles/announcing-the-artificial-analysis-speech-to-speech-index)
44. [GPT-Live vs GPT-Realtime-2 vs Gemini Live in 2026 - Micdrop](https://micdrop.dev/blog/gpt-live-vs-gpt-realtime-vs-gemini-live)
45. [Step-Audio-R1 Technical Report](https://arxiv.org/pdf/2511.15848)
46. [OpenAI vs Gemini vs Qwen Realtime Voice API \[2026\]](https://tech-insider.org/openai-vs-google-vs-qwen-voice-ai-apis-2026/)
47. [Handling input events with the bidirectional API - Amazon Nova](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-input-events.html)
48. [Speech-to-Speech (Amazon Nova 2 Sonic) - Amazon Nova](https://docs.aws.amazon.com/de_de/nova/latest/nova2-userguide/using-conversational-speech.html)
49. [Speech-to-Speech (Amazon Nova 2 Sonic) - Amazon Nova](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html)
50. [Amazon Nova 2 Sonic Explained: AWS's Native Speech-to-Speech Model](https://miraflow.ai/blog/amazon-nova-2-sonic-speech-to-speech-explained-2026)
51. [Chat](https://dev.hume.ai/reference/speech-to-speech-evi/chat)
52. [Session Settings](https://dev.hume.ai/voice/docs/speech-to-speech-evi/configuration/session-settings)
53. [Hume EVI — Agent Patterns Catalog](https://www.agentpatternscatalog.org/compositions/hume-evi/)
54. [Empathic Voice Interface FAQ](https://dev.hume.ai/docs/speech-to-speech-evi/faq)
55. [Hume EVI](https://rywalker.com/research/hume-evi)
56. [Beyond Short Segments : Expanding Speaker Embeddings with Vector Archives](https://arxiv.org/pdf/2609.25007)
57. [diart · PyPI](https://pypi.org/project/diart/)
58. [Wespeaker: A Research and Production oriented Speaker Embedding Learning Toolkit](https://arxiv.org/pdf/2210.17016)
59. [FASTDIAR: Frame-level speaker encoder for Streaming Diarization](https://www.alphaxiv.org/abs/2610.02941)
60. [Real-Time Diarization for Developers: Practical Guide](https://opentranscription.io/blog/real-time-diarization)
61. [FASTDIAR: FrAme-level speaker encoder for STreaming DIARization](https://arxiv.org/html/2610.02941v1)
62. [emee-ai/Sortformer-Diarization · Hugging Face](https://huggingface.co/emee-ai/Sortformer-Diarization)
63. [pyannote/speaker-diarization-3.1 · Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1)
64. <https://www.fon.hum.uva.nl/archive/2009/2009-brm-JongWempe.pdf>
65. [Speech rate is used as a measure of fluency in second](https://link.springer.com/content/pdf/10.3758/BRM.41.2.385.pdf)
66. [Choosing a threshold for silent pauses to measure second ...](https://pure.mpg.de/rest/items/item_1900232_6/component/file_1900231/content)
67. [Choosing a threshold for silent pauses to measure second ...](https://www.isca-archive.org/diss_2013/jong13_diss.pdf)
68. <https://eprints.lancs.ac.uk/id/eprint/152963/>
69. [The Relationship Between Utterance and Perceived Fluency: A Meta‐Analysis of Correlational Studies - SUZUKI - 2021 - The Modern Language Journal - Wiley Online Library](https://onlinelibrary.wiley.com/doi/10.1111/modl.12706)
70. [Exploring measures and perceptions of fluency in the speech of](https://core.ac.uk/download/pdf/70765.pdf)
71. [Aspects of fluency across assessed levels of speaking proficiency Article](https://centaur.reading.ac.uk/84796/1/Accepted%20draft%2007-07-2019.pdf)
72. [(PDF) Aspects of Fluency Across Assessed Levels of Speaking Proficiency](https://www.researchgate.net/publication/338822062_Aspects_of_Fluency_Across_Assessed_Levels_of_Speaking_Proficiency)
73. [Speaking rate consistency in native and non-native speakers of English](https://pubs.aip.org/asa/jasa/article/138/3/EL223/680255/Speaking-rate-consistency-in-native-and-non-native)
74. [Wait! Time!](https://readingforlearning.org/2025/10/25/wait-time/)
75. [Wait Time in Education: 3 Seconds That Change the Answer](https://www.structural-learning.com/post/wait-time-a-teachers-guide)
76. [Wait for It! Improving Student Responses by Increasing Wait Time - The K. Patricia Cross Academy](https://kpcrossacademy.ua.edu/wait-for-it-improving-student-responses-by-increasing-wait-time/)
77. [The Effect of Foreign Accent and Speaking Rate on Native Speaker](https://assess.ucr.edu/sites/default/files/2019-02/anderson-hsiehkoehler_1988.pdf)
78. [(PDF) An Acoustic Study of Real and Imagined Foreigner-Directed Speech](https://www.researchgate.net/publication/228349838_An_Acoustic_Study_of_Real_and_Imagined_Foreigner-Directed_Speech)
79. [(PDF) The Effects of Speaking Rate on Listener Evaluations of Native and Foreign-Accented Speech](https://www.academia.edu/38286250/The_Effects_of_Speaking_Rate_on_Listener_Evaluations_of_Native_and_Foreign_Accented_Speech)
80. [Gemini Live API plugin](https://docs.livekit.io/agents/models/realtime/plugins/gemini/)
81. [Lucida AI — Practice Speaking English with an AI Tutor](https://getlucida.com/)
82. [Lucida vs Duolingo: Which App Gets You Speaking?](https://getlucida.com/lucida-vs-duolingo)
83. [Corporate Language Training with AI Coaching](https://getlucida.com/corporate-language-training)
84. [Lucida AI: Reviews, Features, Pricing, Guides, and Alternatives](https://aipure.ai/products/lucida-ai)
85. [Visualization with pyannote.core](https://colab.research.google.com/github/pyannote/pyannote-audio/blob/develop/tutorials/intro.ipynb)
86. [Playing with Voices: Tabletop Role-Playing Game Recordings as a Diarization Challenge](https://arxiv.org/pdf/2502.12714)
87. [GitHub - BUTSpeechFIT/AMI-diarization-setup · GitHub](https://github.com/BUTSpeechFIT/AMI-diarization-setup)
88. [diarizers-community/ami · Datasets at Hugging Face](https://huggingface.co/datasets/diarizers-community/ami)
89. [legacy-datasets/ami · Datasets at Hugging Face](https://huggingface.co/datasets/legacy-datasets/ami)
90. [mozilla-foundation/common\_voice\_17\_0 · Datasets at Hugging Face](https://huggingface.co/datasets/mozilla-foundation/common_voice_17_0)
91. [FAQ: Can I get the Common Voice or other MDC datasets from other platforms like GitHub or Hugging Face?](https://community.mozilladatacollective.com/faq-can-i-get-the-common-voice-or-other-mdc-datasets-from-other-platforms-like-github-or-hugging-face/)
92. [mozilla-foundation/common\_voice\_13\_0 · Datasets at Hugging Face](https://huggingface.co/datasets/mozilla-foundation/common_voice_13_0)
93. [GitHub - common-voice/cv-dataset: Metadata and versioning details for the Common Voice dataset · GitHub](https://github.com/common-voice/cv-dataset/)
94. [Mozilla Data Collective Alpha Goes Live](https://community.mozilladatacollective.com/mozilla-data-collective-alpha-goes-live/)
95. [FAQ: Why can’t I download old versions of Common Voice datasets?](https://community.mozilladatacollective.com/faq-why-cant-i-download-old-versions-of-common-voice-datasets/)

# Pulsar: grup sohbetindeki herkesi tanıyan sesli dil koçu (mimari)

> **Durum:** Kararlar verildi (2026-11-06), kod henüz yok.
> **Bağlam:** Speech-to-speech AI ile grup halinde İngilizce konuşma pratiği üzerine küçük ölçekli bir demo.
> **İsim:** Pulsar, düzenli aralıklarla "nabız" gibi sinyal yayan nötron yıldızı.
> **İlgili dosyalar:** Kararlar ve gerekçeleri `docs/KARARLAR.md`'de. Teknik araştırma ve kaynaklar `docs/ARASTIRMA.md`'de.
> Bu dosyadaki sayıların kaynağı ARASTIRMA.md. "Ölçülecek" diye işaretlenenler bizim ölçeceğimiz değerler.

---

## 1. Ne yapmaya çalışıyoruz?

AI dil koçu uygulamaları (Lucida, Praktika, Speak vb.) **birebir** konuşma üzerine kurulu. Bu projede şu soruyu soruyoruz:

> **3 kişi aynı online görüşmede İngilizce sohbet ederken, bir AI bu sohbete katılan bir koç olabilir mi?**

Bunun için AI'ın üç şeyi yapabilmesi gerekiyor:

1. **Kim konuşuyor?** Herkesi sesinden tanımak (ses parmak izi / speaker embedding).
2. **Nasıl konuşuyor?** Konuşanın o anki halini sesinden okumak: pitch, enerji, konuşma hızı, duraksamalar (prosodi).
3. **Ona göre cevap vermek:** Doğru kişiye ismiyle, seviyesine ve o anki haline uygun bir tonla, sesli cevap
   vermek (speech-to-speech model).

Ek olarak sistem **kimin ne kadar konuştuğunu** canlı takip edecek ve sessiz kalan kişiyi sohbete dahil edecek.

**Bu proje ne değil:**
- Kendi S2S modelimizi eğitmiyoruz. Hazır bir S2S modelin etrafında ürün ve sistem kuruyoruz.
- Kişinin konuşma tarzını taklit etmiyoruz. Kişiye **uyum** sağlıyoruz: hız, sadelik, cesaretlendirme ve isim.
- Ölçek hedefi yok. 3-4 kişilik tek bir oturum için çalışan bir demo.

---

## 2. Senaryo

1. **Kurulum:** Ahmet, Ayşe ve Mehmet aynı online görüşmede, herkes kulaklık takıyor. Pulsar görüşmeye bir katılımcı
   gibi giriyor.
   - Pulsar konuşmacıları ayrı kanallar halinde değil, **tek bir karışık ses akışı** olarak alıyor. Toplantı botlarının
     çoğu böyle çalışıyor, hibrit odalarda da birkaç kişi tek bir mikrofonu paylaşıyor.
   - Kanal başına ayrı ses gelseydi konuşmacıyı tanımaya gerek kalmazdı. Tek karışık akış en zor durum ve ses parmak
     izini gerekli kılan da bu.
   - Pulsar'ın kendi sesi bu akışa karışmıyor, yani yankı (echo) sorunu yok.
2. **Tanıtım (kişi kaydı):** Herkes sırayla 20-30 saniye kendini tanıtıyor ("Hi Pulsar, I'm Ahmet, I work as …").
   Sistem bu sırada:
   - kişinin ses parmak izini çıkarıyor,
   - kişinin "normal" prosodisini kaydediyor,
   - tanıtım metninden kısa bir profil çıkarıyor: isim, ilgi alanları, tahmini İngilizce seviyesi (CEFR).
3. **Serbest sohbet:** Katılımcılar kendi aralarında konuşuyor. Pulsar dinliyor ama araya girmiyor. Ekranda herkesin
   konuşma payı canlı görünüyor.
4. **Hitap:** Ahmet "Hey Pulsar, how are you?" diye soruyor, Pulsar "I'm good Ahmet, how about you?" diye cevap veriyor.
5. **Takip:** Ahmet "Pulsar" demeden devam ediyor ("Good, thanks. What did you do today?"). Konuşan Ahmet olduğu ve
   Ahmet için bir **takip penceresi** açık olduğu için bu cümle de Pulsar'a gidiyor.
6. **Proaktif soru:** Mehmet uzun süredir az konuşuyor ve ~3 sn sessizlik oluyor. Pulsar sohbetin konusuyla ilgili
   bir soruyu Mehmet'e yöneltiyor.
7. **Tona uyum:** Ayşe kendi normaline göre belirgin şekilde yavaş ve çok duraksayarak konuşuyor. Pulsar ona kısa
   cümlelerle, ~%25 daha yavaş ve cesaretlendirici bir tonla cevap veriyor.

---

## 3. Kısıtlar

- **Donanım:** Apple M2, 8 GB RAM, diskte ~20 GB boş yer. Lokal modeller küçük olmalı. S2S modeli API'den gelecek.
- **Süre:** ~3 gün (Cmt 7 – Pzt 9 Kasım 2026).
- **Bütçe:** Gemini ücretsiz katmanı kullanılacak.
- **Dil:** Katılımcılar ve Pulsar İngilizce konuşacak.
- **Python ortamı:** `uv`, projeye özel `.venv`.
- **Test sesleri:** Açık veri setlerinden (AMI, LibriSpeech) alınacak, gerçek kişi kaydı yapılmayacak. Ücretsiz Gemini
  katmanında Google gönderilen veriyi ürün geliştirmede kullanabiliyor; gerçek kişilerle test yapılırsa ücretli key'e
  geçilmeli.
- **Kapsam dışı:** Yankı engelleme, gerçek bir toplantı platformuna bağlanma, ölçeklenme, mobil uygulama.

---

## 4. Mimari: genel bakış

**Dinleme modu: C-lite.**
- Pulsar sürekli dinliyor. Kimin konuştuğuna, ne dediğine ve kendisine hitap edilip edilmediğine **lokal olarak** karar veriyor.
- Buluttaki S2S modele **sadece Pulsar'a söylenen turlar** gidiyor.
- "Lite" demek, sürekli yazıya döküm (streaming ASR) yapılmaması demek. Her tur bitince o tur tek seferde yazıya dökülüyor.

```
  Karışık toplantı sesi (mikrofon) veya replay WAV
          │  16 kHz mono, 32 ms bloklar
          ▼
  ┌──────────────────────────────────────────────────────┐
  │ Ses girişi → halka tampon (son ~30 sn)                │
  └──────────────┬───────────────────────────────────────┘
                 ▼
          ┌─────────────┐   konuşma başladı / bitti, sessizlik süresi
          │ Silero VAD  │──────────────────────────────────────┐
          └──────┬──────┘                                      │
                 │ tur (konuşma segmenti)                      │
                 ▼                                             ▼
  ┌──────────────────────────────────────────┐    ┌───────────────────────┐
  │ TUR İŞÇİSİ (lokal, paralel)              │    │ Konuşma sayacı         │
  │ • Konuşmacı: WeSpeaker ResNet34 → "Ayşe" │───►│ (kişi başı süre, %)    │
  │ • Prosodi: parselmouth → z-skorlar       │    │ + proaktif politika    │
  │ • ASR: parakeet-mlx → metin + kelime     │    └──────────┬────────────┘
  │   zamanları                              │               │ "Mehmet'e sor"
  │ • Hitap kuralları → Pulsar'a mı?         │               │
  └──────────────┬───────────────────────────┘               │
        hayır ◄──┤ evet                                      │
   (sadece kayıt)│                                           │
                 ▼                                           ▼
  ┌──────────────────────────────────────────┐   ┌─────────────────────────┐
  │ Ton kontrolcüsü (kurallar)               │◄──│ Profil deposu           │
  │ z-skor + profil → ton parametreleri      │   │ ses imzası, normal      │
  └──────────────┬───────────────────────────┘   │ prosodi, CEFR, ilgi     │
                 ▼                               └─────────────────────────┘
  ┌──────────────────────────────────────────┐
  │ COACH NOTE + son konuşmaların özeti      │
  └──────────────┬───────────────────────────┘
                 ▼
  ┌──────────────────────────────────────────┐  WebSocket  ┌──────────────────┐
  │ S2S istemcisi: activityStart → tur sesi  │ ◄─────────► │ Gemini 3.8 Live  │
  │ (tampondan) → not → activityEnd          │             │ (manuel VAD)     │
  └──────────────┬───────────────────────────┘             └──────────────────┘
                 ▼
     Pulsar'ın sesi (24 kHz) → kulaklık

  Her bileşen olayları zaman damgalı bir JSONL günlüğüne yazar. Ölçümler bu günlükten yapılır.
```

**Temel fikir:** Turu S2S model değil **biz yönetiyoruz.** Modelin otomatik tur tespiti kapalı. Önce lokal olarak
kimin ve nasıl konuştuğunu, ayrıca Pulsar'a hitap edilip edilmediğini buluyoruz. Hitap edildiyse turu ve **COACH
NOTE**'u birlikte gönderip turu kapatıyoruz. Model cevaba başladığı anda kime ve nasıl cevap vereceğini zaten biliyor.

**Spekülatif gönderim yok.** Tur, karar verilene kadar lokal tamponda bekliyor. Karar "evet" ise tek seferde
gönderiliyor (5 sn'lik ses ~160 KB, ağdan onlarca ms'de gidiyor). Böylece yanlışlıkla gönderilen bir tur modelin
bağlamında kalmıyor.

**Pahalı işler seyrek, ucuz işler sık çalışıyor:**
- **LLM ile profil çıkarma:** Kişi başına bir kez, tanıtım sırasında.
- **Her turda:** Embedding, prosodi, ASR ve kurallar. Hepsi lokal.

### Süreç yapısı
Tek bir Python süreci, `asyncio` + `sounddevice`:
- `audio_in`: Mikrofon callback'i ayrı bir thread'de çalışıyor ve sadece kuyruğa yazıyor. Replay modunda yerine WAV'ı
  32 ms'lik bloklar halinde gerçek zaman hızında besleyen bir üretici geçiyor.
- `vad_task`: Konuşma turlarını kesiyor.
- `turn_worker`: Embedding, prosodi, ASR ve hitap kararını veriyor. Ağır işler `asyncio.to_thread` ile ayrı thread'de.
- `s2s_sender` / `s2s_receiver`: Gemini ile WebSocket bağlantısı.
- `audio_out`: 24 kHz çalma tamponu. Yeni bir tur ya da `interrupted` mesajı gelince temizleniyor.
- `talktime_monitor`: Konuşma payları ve proaktif soru zamanlayıcısı.
- `jsonl_logger`: Olay günlüğü.
- **Arayüz:** Terminal (`rich`): canlı konuşma payı çubukları ve son olaylar.

---

## 5. Bileşenler

### 5.1 Ses girişi ve halka tampon
- `sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=512)`. Son ~30 sn bellekte tutuluyor, çünkü
  tur hitap kararı verilene kadar burada bekliyor.
- Replay modu kodun geri kalanını değiştirmiyor. Aynı WAV her seferinde aynı olay dizisini üretiyor.

### 5.2 VAD
- **Silero VAD** (~2 MB, CPU'da blok başına < 1 ms).
- Tur sonu için gereken sessizlik varsayılan olarak ~400-600 ms. Zorlanan bir kişi için 700-900 ms'ye çıkıyor
  (bkz. 5.7). Bu sayede kişi cümle ortasında düşünmek için durduğunda tur yarıda kesilmiyor.

### 5.3 Hitap tespiti (kurallar, sıra önemli)
1. Transkriptte "Pulsar" veya ses olarak benzer bir varyantı geçiyor (`pulser`, `pulse are`, `polsar`, …;
   Levenshtein ≤ 2) → **hitap var**.
2. Pulsar'ın son cevabından sonraki **takip penceresi** içinde (soruyla bittiyse 8 sn, bitmediyse 4 sn), Pulsar'ın
   cevap verdiği kişi konuşuyor → **hitap var**.
3. Tur bir soru (soru işareti, wh- kelimesi veya yardımcı fiille başlıyor) **ve** son 30 sn'de Pulsar'a hitap
   edilmiş → **hitap var**.
4. Hiçbiri değilse sadece kayıt tutuluyor ve konuşma süresi güncelleniyor.

Belirsiz durumda Pulsar sessiz kalıyor, çünkü sohbeti gereksiz yere bölmek kötü bir deneyim. Literatürde de sinyal
ailesi aynı: transkript, konuşmacı, akustik özellikler ve önceki etkileşim (Amazon, Apple, Microsoft; ARASTIRMA §1).
Varyant listesi, tanıtım sırasında herkesin "Hey Pulsar" demesiyle ASR'nin bu kelimeyi nasıl yazdığına bakılarak
genişletilecek.

### 5.4 Konuşmacı tanıma (ses parmak izi)
- **Model:** WeSpeaker ResNet34-LM (256 boyut), `wespeaker` paketi ve ONNX ile.
  - VoxCeleb1-O'da EER %0,72, CPU'da pencere başına ~30-50 ms.
  - Yedek: CAM++ (2 kat daha hızlı).
- **Kayıt:** Tanıtım 2 sn'lik, %50 örtüşen parçalara bölünüyor → her parçanın embedding'i L2-normalize ediliyor →
  ortalaması alınıp tekrar normalize ediliyor, bu kişinin **merkez vektörü** oluyor. Parçalar arası benzerliklerin
  5. yüzdeliği kişiye özel bir eşik adayı olarak saklanıyor.
- **Tanıma kuralı:** `en_iyi ≥ τ` **ve** `en_iyi − ikinci ≥ m` ise o kişi, değilse `unknown`.
  - Başlangıç değerleri τ ≈ 0,45-0,55 ve m ≈ 0,08-0,12. Bunlar tahmin; AMI üzerinde grid search ile seçilecek.
  - Hedef: yanlış isimle hitap oranı < %2 olacak şekilde `unknown` oranını en aza indirmek.
- **Yumuşatma:** Konuşmacı değişmemiş görünüyorsa önceki turun etiketine küçük bir öncelik (prior) veriliyor.
- **`unknown` durumunda** Pulsar "Sorry, who asked that?" diyor. Yanlış kişiye ismiyle cevap vermek bundan kötü.
- **Gerçekçi beklenti:** VoxCeleb rakamları gerçek toplantı koşullarında çok iyimser kalıyor. 1 sn'lik seste EER
  %18'e, gerçek toplantıda tek pencerede ~%25'e çıkıyor (ARASTIRMA §12). Bu yüzden turun tamamı kullanılıyor
  (çoğunlukla ≥ 1,5 sn) ve doğruluk AMI üzerinde **ölçülüp raporlanacak**.

### 5.5 Prosodi
| Özellik | Nasıl | Not |
|---|---|---|
| Pitch (F0) | `praat-parselmouth`, `to_pitch_ac`; floor/ceiling kişinin kaydından | Medyan ve 10.-90. yüzdelik aralığı |
| Enerji | Yoğunluk (dB) | Medyan |
| Konuşma hızı | ASR kelime zamanları + `pyphen` ile hece sayısı ÷ süre | Yedek ve tutarlılık kontrolü: de Jong & Wempe hece çekirdeği yöntemi |
| Duraksamalar | Tur içindeki ≥ **250 ms** sessizlikler: sayı, ortalama süre | 250 ms literatürde önerilen eşik |
| Mean length of run (MLR) | İki duraksama arasındaki ortalama hece sayısı | Akıcılığın en güçlü göstergelerinden |
| Cümle ortası duraksama | Kelime zamanlarına göre cümlenin ortasına düşen duraksamalar | A2/B1 seviyesini üst seviyelerden ayırıyor |

- Her özellik, kişinin tanıtımdaki ortalama ve standart sapmasına göre **z-skora** çevriliyor.
- **"Zorlanıyor" sinyali:** hız z ≤ −1 **ve** (MLR z ≤ −1 **veya** cümle ortası duraksama z ≥ +1) **ve** ortalama
  duraksama > ~900 ms.
  - Bunlardan ikisi tutarsa → `struggling`.
  - Biri tutarsa → `slightly_slow`.
- **Kapalı döngü:** Aynı ölçümler Pulsar'ın kendi cevabına da uygulanıyor. "Daha yavaş" dediğimizde gerçekten
  yavaşlıyor mu, ölçülecek (M6).

### 5.6 Profil deposu
Kişi başına bir JSON kaydı, sadece bellekte tutuluyor ve oturum sonunda siliniyor (ayrıca `pulsar forget <isim>` komutu var):
```json
{
  "id": "p1", "name": "Ahmet",
  "embedding_centroid": [/* 256 float */], "self_sim_p5": 0.61,
  "prosody_baseline": {"f0_median": 118.2, "f0_range": 64.0, "intensity_db": 62.1,
                        "speech_rate": 3.4, "mlr": 5.1, "pause_mean_ms": 520},
  "profile": {"cefr": "B1", "interests": ["football", "coding"]},
  "speaking_seconds": 0.0
}
```

### 5.7 Ton kontrolcüsü
1. **Tanıtımda, kişi başına bir kez:** Tanıtım transkriptinden LLM ile `profile` çıkarılıyor (CEFR, ilgi alanları).
   Bunun için ayrı bir LLM key'i gerekmesin diye ücretsiz Gemini'nin metin modeli kullanılacak.
2. **Her turda, kurallarla** (kaynaklar ARASTIRMA §19):

| Durum | Parametre |
|---|---|
| Normal | Doğal hız. Cümle uzunluğu CEFR'e göre: A2 ≤ 8 kelime, B1 ≤ 12, B2+ doğal. En fazla 2 cümle ve 1 soru |
| `slightly_slow` | Biraz daha kısa cümle, kolay kelimeler |
| `struggling` | "~25% slower than normal, natural pauses between sentences" (aşırı yavaşlatma yok). Önce kısa bir onay ("Good point, Ayşe."), sonra kolay bir soru. O kişi için VAD tur sonu sessizliği 700-900 ms'ye çıkıyor |
| Kişi normaline döndü | Uyum kalkıyor. Aşırı uyum (patronizing) riskine karşı sadece z-eşiği aşılınca uyum yapılıyor |

- Bu parametreler COACH NOTE içinde doğal dil talimatı olarak gidiyor. Gemini'de hız için ayrı bir parametre yok.
- Her turda LLM yok, çünkü cevaba gecikme ekler ve kararları görünmez olur.

### 5.8 Tur yöneticisi (durum makinesi)

| Durum | Ne oluyor | Geçiş |
|---|---|---|
| `IDLE` | Sohbet akıyor. Turlar lokal olarak işleniyor, sayaç güncelleniyor | Hitap var → `SENDING`. Proaktif şart sağlandı → `PROACTIVE` |
| `SENDING` | activityStart → tamponda bekleyen tur sesi → COACH NOTE → activityEnd | → `WAITING` |
| `WAITING` | Modelin cevabı bekleniyor | İlk ses parçası geldi → `PULSAR_SPEAKING`. Zaman aşımı (model sessiz kaldı) → olay kaydı, `IDLE` |
| `PULSAR_SPEAKING` | Pulsar konuşuyor | Cevap bitti → `FOLLOW_UP(kişi, 4 veya 8 sn)` |
| `FOLLOW_UP` | Sadece o kişi için pencere açık | Aynı kişinin turu → hitap kuralı 2. Süre doldu → `IDLE` |
| `PROACTIVE` | Modele sadece metin talimatı gidiyor | → `WAITING` |

`WAITING` durumundaki zaman aşımı, Gemini 3.8'in kapatılamayan "proactive audio" özelliği yüzünden var: model bir
girdiyi ilgisiz bulursa cevap vermeyebiliyor (bkz. §8 Risk 1).

### 5.9 S2S istemcisi: Gemini 3.8 Live
- **Model:** `gemini-3.8-live`, ücretsiz katman. Yedek: `gemini-2.5-flash-native-audio-preview-12-2025`. Bu modelde
  proactive audio kapatılabiliyor ve affective dialog da var.
- **Kurulum:** `response_modalities=["AUDIO"]`, `realtime_input_config={"automatic_activity_detection": {"disabled": True}}`,
  `session_resumption={}`, `context_window_compression={"sliding_window": {}}`, düşük düşünme seviyesi.
- **Hitap edilen bir tur:**
  `activity_start` → ses blob'ları (`audio/pcm;rate=16000`) → COACH NOTE → `activity_end`.
  - COACH NOTE iki şekilde gönderilebilir: aktivite penceresinin içinde `send_realtime_input(text=…)` ile, veya
    `send_client_content(…, turn_complete=False)` ile. Hangisinin sıralamayı garanti ettiği **Cumartesi denenecek**.
  - `turn_complete=True` modelin üretimini koşulsuz kesiyor, bu yüzden not gönderirken kullanılmayacak.
- **Proaktif soru:** `send_client_content(turns=[talimat], turn_complete=True)` ile sadece metin gönderip sesli
  cevap alınıyor.
- **Sistem talimatına yazılacak sabit kurallar:** Pulsar bir İngilizce konuşma koçu. Kimin konuştuğunu **sadece
  COACH NOTE söyler**, model sesten tahmin etmez. Cevaplar kısa olur, kişiye ismiyle hitap edilir.
- **COACH NOTE örneği:**
  `[COACH NOTE] Speaker: Ayşe (B1). Now: slower than her baseline (z=-1.4), many mid-clause pauses (z=+1.8).
  Reply to Ayşe by name. ≤2 short sentences, simple B1 words, ~25% slower, warm, end with an easy question.`
- **Oturum yönetimi:**
  - Bağlantı ~10 dakikada bir yenileniyor. `GoAway` mesajı gelince `new_handle` ile yeniden bağlanılıyor.
  - Sistem talimatı bağlantı açıkken değiştirilemiyor.
- **Çıkış:** 24 kHz PCM16.
- **Değiştirilebilir arayüz:** `send_turn(audio, note)`, `send_text(instr)`, `on_audio`, `on_done`. OpenAI Realtime
  sonradan bu arayüze eklenebilir (opsiyonel; doğrudan `speed` parametresi var).

### 5.10 Konuşma sayacı
- Her VAD turu (gerekirse 1,5 sn'lik alt pencereler) en yakın profile atanıyor ve o kişinin süresine ekleniyor.
- `unknown` ve örtüşen konuşma sayaca katılmıyor. Tam diarization yok, çünkü kapalı ve kayıtlı 3 kişilik bir grup var.

### 5.11 Proaktif politika
Pulsar'ın araya girmesi için üç şartın birlikte sağlanması gerekiyor:
1. ≥ 3 sn sessizlik (literatürdeki "wait time" bulgusuyla uyumlu),
2. bir kişinin konuşma payının < %15 olması (ilk 2 dakikadan sonra),
3. son proaktif müdahaleden beri ≥ 60 sn geçmiş olması.

Sorunun konusu, son ~2 dakikanın lokal transkriptinden çıkarılıyor. Bu transkript sadece bellekte tutuluyor.

### 5.12 Olay günlüğü
- JSONL'e sadece olaylar ve sayısal özellikler yazılıyor, metin yazılmıyor: `vad_start`, `vad_end`, `speaker`
  (skor, marj), `prosody` (z-skorlar), `asr_ms`, `addressed` (hangi kural), `send_start`, `activity_end`,
  `first_audio`, `response_done`, `model_silent`, `proactive`.
- Gecikme kırılımı ve doğruluk ölçümleri bu günlükten hesaplanıyor.

---

## 6. Hitap edilen bir turun zaman çizelgesi

```
T          kişi sustu (VAD)
T+~500ms   tur sonu kesinleşti (sessizlik eşiği)
  ├─ embedding  (~30-50 ms)  ┐
  ├─ prosodi    (~30-100 ms) ├ paralel
  └─ ASR        (~150 ms)    ┘  → hitap kararı
T+~700ms   tur sesi + COACH NOTE gönderildi, activity_end
T+~?       Gemini'nin ilk ses parçası (TTFB; bağımsız ölçümlerde 0,6-3 sn arası, kendimiz ölçeceğiz)
```
Hedef: kişinin susmasından Pulsar'ın konuşmaya başlamasına kadar < 1,5 sn. Mümkün ama garanti değil. Gecikme
kırılımı demoda gösterilecek.

---

## 7. Ölçüm planı

| # | Ne ölçülüyor | Veri |
|---|---|---|
| M1 | Konuşmacı tanıma: doğruluk, `unknown` oranı ve **yanlış isim** oranı, tur uzunluğuna göre (1/2/4 sn) | AMI Mix-Headset, LibriSpeech |
| M2 | τ ve m eşik seçimi (grid search), kayıt süresi etkisi (10/20/30 sn), tek embedding ile parça ortalaması karşılaştırması | AMI |
| M3 | Konuşma payı hatası (RTTM etiketleriyle karşılaştırma) | AMI |
| M4 | Hitap kuralları: yanlış tetiklenme ve kaçırma oranı | AMI (yanlış tetiklenme; toplantıda kimse "Pulsar" demiyor) + "Pulsar" içeren senaryo replay'leri |
| M5 | Gecikme kırılımı | Canlı Gemini |
| M6 | Ton gerçekten değişiyor mu? (Pulsar'ın cevabındaki konuşma hızı ve cümle uzunluğu, normal moda göre) | Gemini cevapları |
| M7 | Proactive audio: hitap edilen turların kaçında model sessiz kaldı | Canlı Gemini |
| M8 | RAM ve CPU kullanımı (parakeet + WeSpeaker + VAD birlikte) | Lokal |

**Test için TTS (yapay) ses kullanılmayacak.** TTS sesleri doğruluğu şişirir ve prosodileri yapaydır.
AMI toplantıları 4 kişilik. Bir konuşmacı kayıt dışı bırakılarak "kayıtsız kişi" (`unknown`) senaryosu da test edilecek.

---

## 8. Riskler

1. **Gemini 3.8'de proactive audio kalıcı olarak açık:** Model hitap edilen bir tura bile sessiz kalabilir.
   → Cumartesi **ilk iş** test edilecek. Sorun varsa 2.5 native audio modeline geçilecek.
2. **Ses parmak izinin gerçek toplantı verisindeki doğruluğu:** VoxCeleb'deki değerlerden çok düşük olacak.
   → Temkinli eşik, `unknown` durumu, önceki etikete öncelik, ölçüp dürüstçe raporlamak.
3. **8 GB RAM:** Parakeet'in fp32 ağırlıkları 2,5 GB. → İlk gün ölçülecek, gerekirse daha küçük (bf16) sürüm.
4. **Ücretsiz katman limitleri yayımlanmamış:** Oturum sayısı veya süre limitine takılırsak geliştirmede replay
   ve kayıtlı cevaplar kullanılacak.
5. **Gemini 3.8 bilgileri yeni:** Model adları, fiyatlar ve davranışlar Eylül-Ekim 2026 kaynaklarından. Kod yazmadan
   önce resmi dokümana bakılacak.
6. **Bilinen sınırlar:** Aynı anda konuşma, 1 sn'den kısa turlar, takip penceresinde başka birine sorulan soru,
   kulaklık varsayımı.
7. **Gizlilik:**
   - Ses imzaları biyometrik veri. Sadece bellekte tutuluyor, ham ses saklanmıyor.
   - Transkript sadece bellekte, son ~2 dakika.
   - Buluta sadece hitap edilen turlar gidiyor.
   - Gerçek kişilerle kullanımda açık rıza ekranı ve ücretli katman gerekiyor.

---

## 9. Geliştirme planı

| Zaman | İş |
|---|---|
| **Cmt sabah** | ① **Gemini risk testi:** manuel VAD ile sabit bir WAV turu + COACH NOTE (iki gönderim yolu) → cevap geliyor mu, TTFB, sessiz kalma durumu. ② uv iskeleti, ses giriş/çıkışı, asyncio kuyrukları, JSONL günlüğü, replay modu |
| **Cmt öğleden sonra** | Silero VAD ile tur kesme. Kişi kaydı (2 sn parçalar). Tanıma kuralı. AMI ve LibriSpeech indirme. M1/M2 |
| **Paz sabah** | parselmouth ile prosodi ve z-skorlar, "zorlanıyor" sinyali. parakeet-mlx ile ASR ve kelime zamanları. M8 |
| **Paz öğleden sonra** | Hitap kuralları, takip penceresi, ton kuralları, COACH NOTE. Uçtan uca replay. M3/M4 |
| **Pzt sabah** | Konuşma sayacı arayüzü, proaktif politika, sistem talimatı ayarları. M5/M6/M7 |
| **Pzt öğleden sonra** | Uçtan uca prova, README (İngilizce), demo videosu |

---

## 10. Teknoloji yığını

| Katman | Seçim |
|---|---|
| Ses giriş/çıkış | `sounddevice`, `asyncio` |
| VAD | `silero-vad` |
| Konuşmacı | WeSpeaker ResNet34-LM (`wespeaker`, ONNX); yedek CAM++ |
| ASR | `parakeet-mlx` (`parakeet-tdt-0.6b-v3`), tur sonunda |
| Prosodi | `praat-parselmouth`, `pyphen` |
| S2S | Gemini 3.8 Live (`google-genai`); yedek 2.5 native audio |
| Profil LLM'i | Gemini metin modeli (ücretsiz katman) |
| Arayüz | `rich` (terminal) |
| Veri | AMI Mix-Headset (test bölümünden 3-4 toplantı), LibriSpeech test-clean |

---

## 11. Kalan açık noktalar (ölçümle veya denemeyle çözülecek)

1. COACH NOTE'u Gemini'ye hangi yolla göndermek daha güvenilir: `send_realtime_input(text)` mi,
   `send_client_content(turn_complete=False)` mi? (Cumartesi)
2. Proactive audio sessizlik oranı kabul edilebilir mi, yoksa 2.5 native audio modeline mi geçilmeli? (Cumartesi)
3. τ, m, takip penceresi süreleri, VAD sessizlik eşikleri. (Ölçümle)
4. Parakeet RAM kullanımı 8 GB'a sığıyor mu? (Pazar)
5. OpenAI Realtime ile karşılaştırma yapılacak mı? (Zaman kalırsa)

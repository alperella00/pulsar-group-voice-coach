# Ses parmak izi: AMI gerçek toplantı testi (2026-11-06)

Script: `scripts/speaker_id_ami.py`. Ham sonuçlar: `speaker_id_ami.json`.

**Veri:** AMI test bölümünden 4 toplantı (ES2004a, IS1009a, TS3003a, EN2002a). Her toplantıda 4 kişi var, toplam
16 konuşmacı ve ~92 dakika ses. Kullanılan kayıt Mix-Headset: herkesin yaka mikrofonunun toplamı, yani online
görüşmedeki karışık akışa en yakın kayıt.

**Kurgu:**
- **Temiz konuşma:** RTTM etiketlerinden, sadece tek bir kişinin konuştuğu anlar alınıyor (örtüşmeler çıkarılıyor).
  Konuşma zamanının %5-27'si örtüşüyor.
- **Kayıt:** Her kişinin toplantıdaki ilk temiz konuşmasından min(25 sn, temiz konuşmasının yarısı) kadar.
  3 kişi az konuştuğu için daha kısa sesle kaydedildi: 14,4 / 11,2 / 9,9 sn.
- **Test:** Kayıtta kullanılmayan temiz aralıklar. İki tür:
  - sabit uzunluk (1/2/4 sn),
  - **doğal tur**: aralığın tamamı (1-8 sn, medyan ~2,6 sn).
  - Kişi başı en fazla 80 test.
- **Senaryolar:**
  - 4 kişi kayıtlı,
  - 3 kişi kayıtlı + 1 kayıtsız: her kişi sırayla kayıt dışı bırakılıyor ve onun sesi "kayıtsız kişi" testi oluyor.
- **Konuşma payı:** RTTM'de konuşma olan her 1,5 sn'lik pencere en yakın profile atanıyor. Burada konuşmanın
  nerede olduğunu RTTM'den aldığımız için mükemmel bir VAD varsayılmış oluyor.

## Sonuçlar

**Eşiksiz (top-1) doğruluk:**

| Kayıtlı kişi | 1 sn | 2 sn | 4 sn | doğal tur |
|---|---|---|---|---|
| 4 | %87,7 | %94,5 | %99,6 | %94,9 |
| 3 | %90,5 | %95,9 | %99,7 | %96,1 |

**Eşikli, 3 kişi kayıtlı + 1 kayıtsız:**

| Test | Ayar | Doğru | unknown | yanlış isim | kayıtsız kabul |
|---|---|---|---|---|---|
| 2 sn | başlangıç (τ=0,5, m=0,1) | %73,3 | %26,0 | %0,6 | %3,8 |
| 2 sn | LibriSpeech ızgarası (τ=0,3, m=0,05) | %92,2 | %6,5 | %1,3 | %30,4 |
| doğal tur | başlangıç (τ=0,5, m=0,1) | %80,2 | %18,8 | %1,0 | %2,2 |
| doğal tur | LibriSpeech ızgarası (τ=0,3, m=0,05) | %92,7 | %4,9 | **%2,4** | %31,7 |
| doğal tur | **AMI ızgarası (τ=0,45, m=0,05)** | **%88,8** | **%9,4** | **%1,9** | **%10,1** |

**Konuşma payı** (4 kişi kayıtlı, τ=0,3/m=0,05; `unknown` pencereler sayılmıyor):

| Toplantı | Örtüşme | Gerçek pay (%) | Tahmin (%) | Ortalama hata | unknown pencere |
|---|---|---|---|---|---|
| ES2004a | %16 | 42 / 29 / 18 / 11 | 43 / 35 / 12 / 10 | 3,2 puan | %10,6 |
| IS1009a | %14 | 59 / 10 / 10 / 21 | 57 / 4 / 7 / 32 | 5,7 puan | %21,2 |
| TS3003a | %5 | 3 / 83 / 4 / 11 | 7 / 82 / 2 / 9 | 2,4 puan | %18,7 |
| EN2002a | %27 | 21 / 35 / 20 / 24 | 33 / 32 / 19 / 17 | 6,2 puan | %10,2 |

## Yorum

1. **Gerçek toplantı, temiz sesli kitaptan kötü çıkmadı; biraz daha iyi bile çıktı.** 3 kişi, 2 sn'de LibriSpeech %95,2,
   AMI %95,9. Doğal turlarda (medyan 2,6 sn) %96.
   Muhtemel nedeni: AMI'de kayıt ve test **aynı oturumdan** geliyor (aynı mikrofon, aynı oda, aynı gün).
   LibriSpeech'te ise farklı bölümlerden, yani farklı kayıt oturumlarından geliyordu. Ses parmak izini en çok
   bozan şeylerden biri oturum farkı.
   Bu, demo senaryosuyla da uyumlu: kişi görüşmenin başında kayıt oluyor ve aynı görüşmede tanınıyor.
2. **Kayıtsız kişiyi reddetmek ayara çok bağlı.**
   - Başlangıç ayarında (τ=0,5) AMI'de kayıtsız kişi sadece %2-4 oranında kabul ediliyor; LibriSpeech'te bu %32'ydi.
     Aynı oturumda gruptaki kişilerin skorları yüksek çıkıyor, bu yüzden yüksek eşik yabancıyı ayırabiliyor.
   - Ama LibriSpeech'te seçtiğimiz gevşek ayar (τ=0,3) burada yabancıların %30'unu içeri alıyor ve doğal turlarda
     yanlış isim oranı **%2,4** ile hedefin üstüne çıkıyor.
   - **Sonuç:** Eşik veri setinden veri setine taşınmıyor. AMI'nin kendi ızgarasında bulunan ayar (τ=0,45, m=0,05)
     daha dengeli: doğru %88,8, unknown %9,4, yanlış isim %1,9, kayıtsız kabul %10,1.
3. **Konuşma payı tahmini ortalama 2-6 puan sapıyor.** En kötüsü, en çok örtüşmenin olduğu EN2002a (%27 örtüşme,
   6,2 puan). Pencerelerin %10-21'i `unknown` kaldı. Canlı göstergede kimin az konuştuğunu göstermeye yetiyor, ama
   kesin bir ölçüm değil.
4. **Sınırlar:**
   - 16 konuşmacı var ve test sayıları dengesiz: çok konuşan kişiler kişi başı 80 teste kadar çıkıyor, az konuşan
     bazı kişilerin 1-4 testi var.
   - Kayıt, toplantının içinden kesik parçaları birleştirerek yapıldı. Demodaki kesintisiz tanıtım muhtemelen daha
     temiz bir profil verir.
   - Konuşma payında VAD yerine RTTM kullanıldı; gerçek VAD'ın hataları bu ölçüme dahil değil.

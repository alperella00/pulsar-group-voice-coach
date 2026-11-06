# Araştırma isteği: küçük kapalı grupta kayıtsız kişiyi reddetmek

> Bu dosya bir deep research isteği olarak hazırlandı. Bağlam, ölçülmüş veriler ve sorular aşağıda.
> Sistemin geri kalanı: `docs/MIMARI.md`. Ölçümün tamamı: `reports/speaker_id_librispeech.md`.

## Bağlam

Pulsar, 3-4 kişilik bir online İngilizce konuşma grubunda (tek karışık ses akışı) kimin konuştuğunu ses
parmak iziyle buluyor:

- **Model:** WeSpeaker ResNet34-LM (256 boyutlu embedding), ONNX, `sherpa-onnx` ile, Apple M2 CPU.
- **Kayıt:** Kişi başı 25 sn → 2 sn'lik, %50 örtüşen parçalar → her parçanın L2 normalize embedding'i →
  ortalama → tekrar normalize (merkez vektör). Parçaların merkeze benzerliğinin 5. yüzdeliği (`self_sim_p5`)
  da saklanıyor.
- **Karar kuralı:** kosinüs benzerliği. `en_iyi ≥ τ` ve `en_iyi − ikinci ≥ marj` ise o kişi, değilse `unknown`.
- **Öncelik:** Yanlış kişiye ismiyle hitap etmek (yanlış isim) en kötü hata, hedef < %2.
  "Kim sordu?" (`unknown`) daha az kötü ama çok sık olursa deneyimi bozuyor.

## Ölçülmüş veriler (LibriSpeech test-clean, 40 kişi; N<40 için 30 rastgele grup; kişi başı 20 test parçası)

Eşiksiz (top-1) doğruluk:

| N | 1 sn | 2 sn | 4 sn |
|---|---|---|---|
| 2 | 92,6 | 97,0 | 98,2 |
| 3 | 89,0 | 95,2 | 97,6 |
| 5 | 81,3 | 92,6 | 95,5 |
| 10 | 71,2 | 87,1 | 93,8 |
| 20 | 61,1 | 82,2 | 91,2 |
| 40 | 53,5 | 78,0 | 88,9 |

Eşikli (τ=0,5, marj=0,1): gruptaki kişiler için doğru / unknown / yanlış isim, ve **kayıtsız kişinin kabul edilme oranı**
(her grup için gruba dahil olmayan 3 kişiden 7'şer parça):

| N | L | doğru | unknown | yanlış isim | kayıtsız kabul |
|---|---|---|---|---|---|
| 2 | 2 sn | 84,2 | 15,4 | 0,4 | **36,2** |
| 3 | 1 sn | 62,6 | 35,5 | 1,9 | **30,8** |
| 3 | 2 sn | 77,6 | 22,0 | 0,4 | **32,2** |
| 3 | 4 sn | 82,9 | 16,7 | 0,4 | **29,2** |
| 5 | 2 sn | 62,5 | 37,2 | 0,3 | 27,6 |
| 10 | 2 sn | 45,6 | 54,1 | 0,2 | 9,0 |
| 20 | 2 sn | 32,7 | 67,3 | 0,1 | 2,5 |

N=3 için ızgara araması (τ 0,30–0,70, marj 0,00–0,30; yanlış isim < %2 şartıyla unknown'u en aza indiren ayar):

| L | τ | marj | doğru | unknown | yanlış isim | kayıtsız kabul |
|---|---|---|---|---|---|---|
| 1 sn | 0,30 | 0,10 | 62,6 | 35,5 | 1,9 | 33,0 |
| 2 sn | 0,30 | 0,05 | 90,6 | 7,9 | 1,4 | **61,6** |
| 4 sn | 0,70 | 0,00 | 96,9 | 1,3 | 1,8 | 27,9 |

Gözlemler:
- Kişi sayısı arttıkça `unknown` oranını patlatan şart eşik değil, marj.
- Küçük grupta yabancı kolayca kabul ediliyor. Eşiği gevşetmek gruptaki kişiler için iyi, yabancılar için kötü.

## Ek veri: AMI gerçek toplantı (4 toplantı, 16 kişi, Mix-Headset)

Kayıt ve test aynı toplantıdan (aynı oturum). Her toplantıda 3 kişi kayıtlı, 4. kişi kayıtsız (her kişi sırayla).
Doğal turlar (1-8 sn, medyan ~2,6 sn):

| Ayar | doğru | unknown | yanlış isim | kayıtsız kabul |
|---|---|---|---|---|
| τ=0,50, m=0,10 | 80,2 | 18,8 | 1,0 | 2,2 |
| τ=0,30, m=0,05 (LibriSpeech ızgarası) | 92,7 | 4,9 | 2,4 | 31,7 |
| τ=0,45, m=0,05 (AMI ızgarası) | 88,8 | 9,4 | 1,9 | 10,1 |

Gözlem: Aynı oturumda gruptaki kişilerin skorları yüksek, bu yüzden yüksek bir τ yabancıyı iyi ayırıyor. Ama
eşik veri setleri arasında taşınmıyor. Ek soru: Eşiği her görüşmenin kendi kayıt verisinden (oturum başında)
otomatik kalibre etmenin bir yolu var mı?

## Sorular

1. **Skor normalizasyonu:** AS-norm, S-norm, Z/T-norm gibi yöntemler, 3-5 kişilik kapalı bir grupta kayıtsız kişiyi
   reddetmeye ne kadar yardım eder? Kohort (normalizasyon için kullanılan dış konuşmacı havuzu) ne kadar büyük olmalı
   ve nereden gelmeli (ör. VoxCeleb embedding'leri)? Gerçek zamanlı maliyeti nedir?
2. **Kişiye özel eşik:** Kayıttan elde edilen `self_sim_p5` gibi istatistiklerle kişi başına eşik belirlemek işe
   yarar mı? Literatürde bunun karşılığı ne?
3. **Açık küme tanıma (open-set identification):** Küçük kapalı gruplarda "bu kişi gruptan biri değil" kararı
   için önerilen yöntemler neler? Ör. kalibrasyon (logistic regression ile skoru olasılığa çevirmek),
   PLDA, "background/other" sınıfı, ekstrem değer yöntemleri.
4. **Kayıtsız kişi kabul oranı ile yanlış isim/unknown arasındaki dengeyi** tek bir hedefe nasıl bağlarız?
   Örneğin bir maliyet fonksiyonu (yanlış isim maliyeti > yabancıyı kabul maliyeti > unknown maliyeti) ve bunu
   optimize eden eşik seçimi.
5. **Zamansal bağlam:** Ardışık turlarda konuşmacı geçiş olasılıkları (HMM benzeri bir öncelik) kısa turlarda
   doğruluğu ne kadar artırır?
6. **Kayıt kalitesi:** 25 sn yerine kayıt sırasında farklı konuşma tarzlarından (soru, kısa cevap, uzun anlatım)
   örnek toplamak, ya da oturum içinde kendinden emin tanımalarla profili güncellemek (online enrollment
   adaptation) yabancı reddini iyileştirir mi? Profil kayması (drift) riski nedir?
7. Bu verilere bakarak 3 kişilik demo için **somut bir öneri**: hangi yöntem, hangi parametreler, uygulaması kaç saat?

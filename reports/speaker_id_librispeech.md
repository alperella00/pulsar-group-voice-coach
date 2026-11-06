# Ses parmak izi: LibriSpeech test-clean (40 konuşmacı)

Model: WeSpeaker ResNet34-LM (ONNX, sherpa-onnx). Kayıt: kişi başı 25 sn, 2 sn parçalar (%50 örtüşme), ortalama merkez vektör. Test: kayıtta kullanılmayan cümlelerden kişi başı 20 parça. N<40 için 30 rastgele grup.

Eşikli kural: en_iyi ≥ 0.5 ve en_iyi − ikinci ≥ 0.1, değilse `unknown`.

| Grup (N) | Parça (sn) | Top-1 doğru (eşiksiz) | Eşikli: doğru | unknown | **yanlış isim** | Kayıtsız kişi kabul edildi |
|---|---|---|---|---|---|---|
| 2 | 1 | %92.6 | %71.8 | %26.9 | **%1.2** | %35.1 |
| 2 | 2 | %97.0 | %84.2 | %15.4 | **%0.4** | %36.2 |
| 2 | 4 | %98.2 | %88.6 | %11.2 | **%0.2** | %35.7 |
| 3 | 1 | %89.0 | %62.6 | %35.5 | **%1.9** | %30.8 |
| 3 | 2 | %95.2 | %77.6 | %22.0 | **%0.4** | %32.2 |
| 3 | 4 | %97.6 | %82.9 | %16.7 | **%0.4** | %29.2 |
| 5 | 1 | %81.3 | %44.5 | %54.0 | **%1.5** | %24.3 |
| 5 | 2 | %92.6 | %62.5 | %37.2 | **%0.3** | %27.6 |
| 5 | 4 | %95.5 | %71.5 | %28.3 | **%0.2** | %26.5 |
| 10 | 1 | %71.2 | %26.9 | %72.2 | **%0.9** | %6.7 |
| 10 | 2 | %87.1 | %45.6 | %54.1 | **%0.2** | %9.0 |
| 10 | 4 | %93.8 | %57.7 | %42.2 | **%0.1** | %12.9 |
| 20 | 1 | %61.1 | %16.4 | %83.2 | **%0.4** | %1.7 |
| 20 | 2 | %82.2 | %32.7 | %67.3 | **%0.1** | %2.5 |
| 20 | 4 | %91.2 | %44.6 | %55.4 | **%0.0** | %6.2 |
| 40 | 1 | %53.5 | %10.2 | %89.6 | **%0.1** | %None |
| 40 | 2 | %78.0 | %24.8 | %75.2 | **%0.0** | %None |
| 40 | 4 | %88.9 | %34.9 | %65.1 | **%0.0** | %None |

## Eşik ızgarası (N=3, yanlış isim < %2 şartıyla unknown'u en aza indiren)

| Parça (sn) | τ | marj | doğru | unknown | yanlış isim | kayıtsız kabul |
|---|---|---|---|---|---|---|
| 1 | 0.3 | 0.1 | %62.6 | %35.5 | %1.9 | %33.0 |
| 2 | 0.3 | 0.05 | %90.6 | %7.9 | %1.4 | %61.6 |
| 4 | 0.7 | 0.0 | %96.9 | %1.3 | %1.8 | %27.9 |

Not: LibriSpeech temiz, tek mikrofonlu sesli kitap kaydı. Gerçek toplantı sesinde (AMI) sonuçlar daha kötü olacak; bu tablo üst sınır olarak okunmalı.

## Yorum

1. **Kişi sayısı arttıkça doğruluk düşüyor.** 2 sn'lik parçada eşiksiz doğruluk: 3 kişide %95, 10 kişide %87,
   40 kişide %78. Bu, MIMARI §11.2'deki "arama grup içinde kalmalı" iddiasının ölçülmüş hali.
2. **1 sn çok kısa.** 3 kişide bile eşiksiz doğruluk %89. Turun tamamı kullanılmalı; 2 sn ve üzeri güvenilir.
3. **Eşik, yanlış isim hatasını her durumda %2'nin altında tuttu.** Hedef buydu. Ama başlangıç ayarlarında
   (τ=0,5, marj=0,1) bunun bedeli yüksek: 3 kişi, 2 sn'de turların %22'si `unknown`. Asıl kısıtlayan şart eşik
   değil, marj: kişi sayısı arttıkça en iyi iki aday birbirine yaklaşıyor.
   Izgara araması 3 kişi ve 2 sn için daha dengeli bir ayar buldu: τ=0,3, marj=0,05 → doğru %90,6,
   `unknown` %7,9, yanlış isim %1,4.
4. **Zayıf nokta: kayıtsız kişiyi reddetmek.** 3 kişilik grupta, kayıtlı olmayan birinin sesi %30 oranında
   gruptan birine atanıyor. Daha gevşek ızgara ayarında bu oran %62'ye çıkıyor. Az aday varken yabancının en
   yakın adayı da kolayca eşiği geçiyor.
   Demo senaryosunda herkes kayıt olduğu için bu ikincil bir sorun. Ama gerçek bir ürün için skor normalizasyonu
   (ör. AS-norm) ya da kişiye özel eşik (`self_sim_p5`) gerekecek.

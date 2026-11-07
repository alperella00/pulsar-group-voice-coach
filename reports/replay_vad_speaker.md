# Uçtan uca replay: VAD turları + ses parmak izi (2026-11-07)

**Komut:** `uv run python -m pulsar --meeting <M> --speed 0` → `logs/replay_<M>.jsonl`;
değerlendirme `uv run python scripts/eval_replay.py ES2004a IS1009a TS3003a EN2002a`.

**Kurgu:**
- 4 AMI toplantısı (Mix-Headset), **4 kişi kayıtlı**. Kayıt RTTM'den: her kişinin ilk temiz konuşması, min(25 sn, temiz/2).
- Turlar artık RTTM'den değil **Silero VAD**'dan geliyor (eşik 0,5, tur sonu sessizliği 500 ms, ön/arka pay 96 ms).
- Her turun ilk 8 sn'si → WeSpeaker → τ=0,45, m=0,05 (K18).
- Turun "sahibi": RTTM'ye göre tur içinde en çok konuşan kişi. Saflık = sahibin süresi / turdaki toplam konuşma.
  Saflık ≥ 0,8 → "tek kişilik tur". Turun yarısından fazlası kayıt aralığındaysa tur sayılmıyor.
- Hız: 92 dk ses ~96 sn'de işlendi (speed=0). Gerçek zaman modunda (speed=1) 60 sn ses 60,1 sn'de bitti.

## Sonuç (tur sonu sessizliği 500 ms)

| Toplantı | Tur | Medyan süre | Yanlış alarm | Tek kişilik | Doğru | Unknown | Yanlış isim |
|---|---|---|---|---|---|---|---|
| ES2004a | 132 | 2,8 sn | %3,8 | %71,7 | %77,2 | %18,9 | %3,9 |
| IS1009a | 86 | 4,1 sn | %11,6 | %69,7 | %77,6 | %9,2 | %13,2 |
| TS3003a | 319 | 1,7 sn | %2,2 | %88,8 | %49,4 | %45,5 | %5,1 |
| EN2002a | 297 | 3,5 sn | %1,0 | %54,1 | %72,8 | %14,6 | %12,6 |

| Toplam | n | Doğru | Unknown | Yanlış isim |
|---|---|---|---|---|
| Tek kişilik turlar | 580 | %65,7 | %30,9 | %3,4 |
| Karışık turlar | 229 | %62,9 | %16,2 | **%21,0** |
| Hepsi | 809 | %64,9 | %26,7 | **%8,4** |
| Süre < 1 sn | 164 | %32,3 | %56,7 | %11,0 |
| 1-2 sn | 181 | %59,1 | %35,4 | %5,5 |
| 2-4 sn | 181 | %76,8 | %18,8 | %4,4 |
| ≥ 4 sn | 283 | %79,9 | %8,8 | %11,3 |

Embedding süresi medyan 82 ms (tur başına, 8 sn'ye kadar ses).

## Tur sonu sessizliği 250 ms (karşılaştırma)
Tur 809 → 1336, karışık tur oranı neredeyse aynı (%28 → %26), yanlış isim %8,4 → %9,4. **İşe yaramadı**; 500 ms kalıyor.

## Ne öğrendik?
1. **RTTM'li ölçüm (doğru %88,8, yanlış %1,9) gerçek akışta iyimser kaldı.** Gerçek VAD turlarında doğru %65, yanlış isim %8,4.
2. **Ana sorun karışık turlar.** VAD konuşma/sessizlik ayırıyor, konuşmacı değişimini bilmiyor. AMI'de konuşmacılar
   çoğu zaman sessizlik bırakmadan söz alıyor; turların ~%28'i birden fazla kişi içeriyor ve bunlarda yanlış isim %21.
   Sessizlik eşiğini kısaltmak bunu çözmüyor (250 ms denemesi).
3. **Kısa turlar (< 1 sn) tanınmıyor:** çoğu "yeah / mm-hmm". Pulsar bunlara zaten cevap vermeyecek; sayaç için önemsiz.
4. **Uzun turlarda (≥ 4 sn) yanlış isim %11:** içinde konuşmacı değişimi olma ihtimali artıyor.
5. **Tek kişilik turlarda yanlış isim %3,4**, unknown %31. Unknown'un yüksekliği kısa turlardan geliyor.
6. **Sınır:** AMI, demo senaryosundan zor: kulaklıklı online görüşmede insanlar daha sırayla konuşur ve Pulsar'a soru
   sorarken net, tek kişilik bir cümle kurar. Ama bu varsayım ölçülmedi.

## Ek: neredeyse tamamen tek kişilik turlar (saflık ≥ 0,95)

| Süre | n | Eşiksiz doğru | Eşikli doğru | Unknown | Yanlış isim |
|---|---|---|---|---|---|
| < 1 sn | 139 | %66,2 | %33,8 | %57,6 | %8,6 |
| 1-2 sn | 148 | %93,9 | %60,8 | %35,8 | %3,4 |
| 2-4 sn | 116 | **%98,3** | %76,7 | %22,4 | %0,9 |
| ≥ 4 sn | 82 | **%100** | %91,5 | %8,5 | %0,0 |

**Yorum:** Tek kişi 2 sn'den uzun konuştuğunda 25 sn'lik kayıttan çıkan profil onu neredeyse her zaman buluyor.
Yanlış isimlerin %68'i karışık turlardan geliyor (68 yanlışın 46'sında seçilen kişi turda gerçekten konuşuyor ama
azınlıkta). Eşik bu turlarda temkinli: 2-4 sn'de %22 unknown. Kısa turlara (< 1 sn) isim vermemek yanlışların %18'ini siler.

## Ek: karışık turlarda üst üste konuşma

- 229 karışık turdaki konuşma süresinin **%35**'inde iki veya daha fazla kişi aynı anda konuşuyor, %65'inde tek kişi
  (arka arkaya, sessizlik bırakmadan söz alma).
- Karışık turlardaki 48 yanlış ismin **45**'inde üst üste konuşma var (tur süresinin > %10'u).
- Sonuç: tek kişilik kısım için turu pencerelerle bölmek yetiyor; üst üste kısım için hedef konuşmacı çıkarma
  (VoiceFilter / SpeakerBeam / WeSep) veya TS-VAD gibi profil koşullu bir model gerekiyor (kullanıcının önerisi,
  2026-11-07: "A'nın sesini bastırıp araya gireni duymak").

## Tur içi bölme (K20) + kısa turlara isim vermeme

`src/pulsar/segment.py`: 1,5 sn pencere / 0,5 sn kayma, yeni isim ≥ 2 pencere sürerse değişim; yakın boşluğa
(±0,75 sn) kaydırma; ≥ 150 ms boşluklarda sol/sağ (1-3 sn) ayrı tanınıp farklı ve netse kesim; < 1 sn alt tura isim yok.
Karşılaştırma aynı eval script'iyle (`logs/base` = bölmesiz, `logs/split` = bölmeli). Bölünen tur: 147.

| | Bölmesiz | Bölmeli |
|---|---|---|
| Konuşma süresine göre doğru kişiye | %57,5 | **%65,7** |
| Konuşma süresine göre yanlış kişiye | %30,3 | **%23,5** |
| Konuşma süresine göre isimsiz | %12,2 | %10,8 |
| Birim başına doğru / unknown / yanlış | %64,9 / %26,7 / %8,4 | %62,6 / %27,4 / %10,1 |
| ≥ 4 sn birimlerde yanlış | %11,3 | **%3,2** |
| 1-2 sn birimlerde yanlış | %5,5 | **%19,4** |
| < 1 sn birimlerde yanlış | %11,0 | %0 (isim verilmiyor) |

Hız: 92 dk ses ~470 sn (gerçek zamanın 9-21 katı). Bölmesiz ~96 sn.

**Yorum:** Uzun karışık turlar bölünüyor ve süreye göre doğruluk +8 puan. Yeni sorun: kesimlerin ürettiği 1-2 sn'lik
parçalar (üst üste konuşma bölgesine düşen ya da kesimi tam oturmayan) %19 yanlış isim veriyor. Not: süre ölçümünde
örtüşen saniyeler iki kişiye de yazıldığından "yanlış kişiye" oranının örtüşmeden gelen bir tabanı var.
**Sonraki adım:** bölünmüş 1-2 sn parçalar için daha sıkı kural (ör. bölünmüş parçada en az 1,5 sn ya da τ'yu bu
veriyle yeniden seçmek).

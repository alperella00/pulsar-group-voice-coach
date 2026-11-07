# Konuşma sayacı, proaktif soru, söz kesme (2026-11-07)

Kod: `src/pulsar/app.py` (tur yöneticisi, sayaç, `proactive_monitor`), `src/pulsar/s2s.py` (`send_text`, `interrupt`,
yeniden bağlanma), `src/pulsar/player.py` (`clear`). Hepsi replay + canlı Gemini 3.8 Live ile denendi.

## Proaktif soru (AMI ES2004a, ilk 330 sn, 4 kişi kayıtlı)
Kural: ≥ 3 sn sessizlik + birinin payı < %15 (ilk 2 dk'dan sonra) + son proaktiften ≥ 60 sn. Sadece metin talimatı.

| | FEE013 | FEE016 | MEE014 | MEO015 |
|---|---|---|---|---|
| Gerçek pay (RTTM, 0-330 sn) | %74,8 | %6,5 | %0,4 | %18,3 |
| Sayaç | %78,7 | %4,2 | %0,0 | %17,1 |

- 188. ve 254. sn'de MEE014'e (gerçekten en sessiz kişi) soru; ilk ses 0,68 / 0,60 sn.
- Soru toplantının gerçek konusuyla ilgili (beyaz tahtaya hayvan çizimi): *"MEE014, what is your favorite animal
  that you would want to draw on the whiteboard?"* → son konuşmaların ASR metni nota ekleniyor.
- **Gemini bağlantıyı ~2 dk sessizlikte kapattı** ("client inactivity", 120. sn); gönderimden önce yeniden bağlanma
  602 ms sürdü. İlk denemede bu yoktu ve proaktif soru hata verdi.
- Sorunlar: aynı kişiye 66 sn arayla neredeyse aynı soru (kişi cevap vermediyse farklı strateji gerekir); AMI'de gerçek
  isim yok, Pulsar "MEE014" diyor.
- İlk deneme iki testi aynı anda çalıştırdığım için bozuldu (işlemci/GPU paylaşıldı, turlar birikti, sayaç geride kaldı,
  hiç sayılmamış kişi "%0" sanıldı). Önlem: işlenmeyi bekleyen tur varken proaktif karar verilmiyor.

## Söz kesme (kullanıcının kayıtları, `scripts/make_scenario.py --barge`)
- Pulsar tanıtıma cevap verirken "Pulsar, what do you think…" → oynatma kesildi, yeni tur gönderildi, cevap 1,44 sn'de.
- Bulunan hata: Pulsar daha ses üretmeden (WAITING) kesilince Gemini "interrupted" göndermiyor; yeni cevabın parçaları
  eski cevabınki sanılıp atıldı ve Pulsar sessiz kaldı. Çözüm: söz kesme sadece PULSAR_SPEAKING'de; WAITING'de atlanır.
- Gemini kesilen üretim için boş bir "bitti" gönderiyor; artık yok sayılıyor (durumu değiştirmesin).
- Sadece isimle hitap (kural 1) söz kesiyor; araya giren "yeah" Pulsar'ı susturmaz.

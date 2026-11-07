# ASR: parakeet-tdt-0.6b-v3 (MLX) (2026-11-07)

Script: `scripts/asr_smoke.py` (tek başına), boru hattı içinde `src/pulsar/asr.py` (`asr` olayı, `asr_ms`).

## Bellek ve hız (tek başına, AMI'den VAD turları)
- MLX tepe bellek **2,0 GB**, süreç RSS tepe ~0,65 GB. Model diskte 4,7 GB (fp32 dosya, bf16 yükleniyor).
- İlk çağrı ~2 sn (MLX derlemesi). Sonra tur başına medyan **~206 ms** (EN2002a, 20 tur, 2-8 sn), gerçek zamanın ~20 katı.
- Kalite (göz kontrolü, WER ölçülmedi): kirli toplantı sesinde metin büyük ölçüde doğru, dolgu sesleri ("um", "uh")
  yazılıyor. Token'lar kelime parçası, zamanlar 80 ms adımlı.

## Boru hattında gecikme sorunu
- Beklemesiz replay (`--speed 0`): ASR tur başına 105-202 ms.
- Gerçek zaman (`--speed 1`): **~550-1100 ms medyan**, p90 1,4-2,2 sn. Fark, süreç turlar arasında boşta beklerken çıkıyor.
- Denenen ve **işe yaramayanlar** (EN2002a 300-480 sn, ≥ 1,5 sn turlar, n=15):

| Ayar | Medyan | p90 |
|---|---|---|
| Önlem yok | 1110 ms | 2188 ms |
| VAD başlangıcında GPU ısıtma (`nudge`) | 853 ms | 1871 ms |
| Isıtma + ASR thread'i QoS USER_INTERACTIVE | 958 ms | 1426 ms |
| (ayrıca) çok boylu açılış ısıtması, GIL geçiş aralığı 0,5/0,1 ms | etkisiz | |

- Sebep doğrulanmadı; en güçlü aday macOS güç yönetimi (boştaki süreç). Doğrulamak için `powermetrics` (sudo) gerekir.
- MLX stream'leri thread'e bağlı: model yüklendiği thread'de çalışmalı → ASR'nin tek kendi thread'i var.

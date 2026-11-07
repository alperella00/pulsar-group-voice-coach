"""Pulsar: grup sohbetinde S2S dil koçu. Canlı sistem (replay ve mikrofon)."""
SR = 16000      # örnekleme hızı: saniyede 16.000 örnek
BLOCK = 512     # blok boyu: 512 örnek = 32 ms (Silero VAD'ın 16 kHz'de istediği boy)

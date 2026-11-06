"""LibriSpeech test-clean'den 3-6 sn'lik gerçek bir insan cümlesi seçip data/smoke/turn.wav olarak yazar."""
from pathlib import Path

import soundfile as sf

ROOT = Path("data/librispeech/LibriSpeech/test-clean")
OUT = Path("data/smoke/turn.wav")

for flac in sorted(ROOT.rglob("*.flac")):
    info = sf.info(flac)
    if 3.0 <= info.duration <= 6.0:
        audio, sr = sf.read(flac, dtype="int16")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        sf.write(OUT, audio, sr, subtype="PCM_16")
        utt = flac.stem
        trans = next(flac.parent.glob("*.trans.txt")).read_text().splitlines()
        text = next(line.split(" ", 1)[1] for line in trans if line.startswith(utt))
        print(f"{utt}  {info.duration:.2f} sn  {sr} Hz\nmetin: {text}")
        break

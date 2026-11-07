"""JSONL olay günlüğü (MIMARI §5.12). Her satır bir olay. Metin yazılmıyor, sadece olaylar ve sayılar.

  t    = medya zamanı (sn): toplantının kaçıncı saniyesinde
  wall = programın başlangıcından beri geçen gerçek süre (ms)
"""
import json
import time
from pathlib import Path


class EventLog:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "w")
        self.t0 = time.monotonic()

    def write(self, event: str, t: float | None = None, **fields) -> None:
        rec = {"event": event, "wall": round((time.monotonic() - self.t0) * 1000, 1)}
        if t is not None:
            rec["t"] = round(t, 3)
        rec.update(fields)
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.f.flush()

    def close(self) -> None:
        self.f.close()

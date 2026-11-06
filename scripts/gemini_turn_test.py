"""Gemini Live risk testi (MIMARI §9, Cumartesi ilk iş).

Sorular:
  1. Manuel tur yönetimi (activity_start / activity_end) çalışıyor mu?
  2. COACH NOTE'u göndermenin iki yolundan hangisi model tarafından okunuyor?
       A) aktivite penceresinin içinde: send_realtime_input(text=...)
       B) turdan önce: send_client_content(..., turn_complete=False)
     Kontrol: notta konuşmacı "Ayşe" olarak veriliyor; cevapta "Ayşe" geçiyorsa not ulaşmış demektir.
  3. Sadece metin talimatıyla (proaktif soru) sesli cevap üretiliyor mu?
  4. Gecikme: activity_end gönderildikten ilk ses byte'ına kadar geçen süre (TTFB).

Her deneme ayrı bir oturumda koşar ki önceki denemeler bağlama karışmasın.
Kullanım: uv run python scripts/gemini_turn_test.py [deneme_sayısı]
"""
import asyncio
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from google import genai
from google.genai import types

# model -> API sürümü (2026-11-06 denemesi: 2.5 sadece v1alpha'da, 3.8 v1beta'da bağlandı)
MODELS = {
    "gemini-3.8-live": "v1beta",
    "gemini-2.5-flash-native-audio-preview-12-2025": "v1alpha",
}
TURN_WAV = Path("data/smoke/turn.wav")  # gerçek insan sesi (LibriSpeech), scripts/pick_smoke_turn.py üretir
OUT_DIR = Path("data/smoke")
LOG = Path("reports/gemini_turn_test.jsonl")

SYSTEM = (
    "You are Pulsar, a friendly English speaking coach in a small group conversation. "
    "Several people share one microphone. Only the COACH NOTE tells you who is speaking; "
    "never guess the speaker from the voice. Address the speaker by the name in the COACH NOTE. "
    "Keep replies short: at most 2 sentences."
)
NOTE = (
    "[COACH NOTE] Speaker: Ayşe (B1). Now: slower than her baseline (z=-1.4), many mid-clause pauses (z=+1.8). "
    "Reply to Ayşe by name. ≤2 short sentences, simple B1 words, ~25% slower, warm, end with an easy question."
)
PROACTIVE = (
    "[COACH NOTE] Mehmet has been quiet for a while. The group is talking about weekend plans. "
    "Ask Mehmet one short, friendly question about his weekend. Use his name."
)


def config() -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM,
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def collect(session, t_end: float) -> dict:
    """Modelin cevabını toplar: ilk ses gecikmesi, toplam ses, cevabın transkripti."""
    first, chunks, text = None, [], []
    async for msg in session.receive():
        if msg.data:
            first = first if first is not None else time.perf_counter() - t_end
            chunks.append(msg.data)
        sc = msg.server_content
        if sc and sc.output_transcription and sc.output_transcription.text:
            text.append(sc.output_transcription.text)
    audio = b"".join(chunks)
    return {
        "ttfb_s": None if first is None else round(first, 3),
        "audio_s": round(len(audio) / 2 / 24000, 2),  # 24 kHz, 16 bit mono
        "reply": "".join(text).strip(),
        "_audio": audio,
    }


async def run_turn(client, model: str, path: str, pcm: bytes) -> dict:
    async with client.aio.live.connect(model=model, config=config()) as s:
        if path == "B":  # not, turdan önce ayrı bir içerik olarak (turu kapatmadan)
            await s.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=NOTE)]), turn_complete=False)
        await s.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(pcm), 3200):  # 100 ms'lik parçalar
            await s.send_realtime_input(audio=types.Blob(data=pcm[i:i + 3200], mime_type="audio/pcm;rate=16000"))
        if path == "A":  # not, aktivite penceresinin içinde
            await s.send_realtime_input(text=NOTE)
        await s.send_realtime_input(activity_end=types.ActivityEnd())
        return await collect(s, time.perf_counter())


async def run_proactive(client, model: str) -> dict:
    async with client.aio.live.connect(model=model, config=config()) as s:
        await s.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=PROACTIVE)]), turn_complete=True)
        return await collect(s, time.perf_counter())


def save_wav(path: Path, audio: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(audio)


async def main(n: int) -> None:
    load_dotenv(".env")
    data, sr = sf.read(TURN_WAV, dtype="int16")
    assert sr == 16000, sr
    pcm = data.astype(np.int16).tobytes()

    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as log:
        for model, ver in MODELS.items():
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"api_version": ver})
            short = "38" if "3.8" in model else "25"
            for trial in range(1, n + 1):
                for kind in ("A", "B", "P"):
                    try:
                        coro = run_proactive(client, model) if kind == "P" else run_turn(client, model, kind, pcm)
                        r = await asyncio.wait_for(coro, timeout=40)
                    except Exception as e:  # noqa: BLE001 - testte her hatayı kaydetmek istiyoruz
                        r = {"error": f"{type(e).__name__}: {str(e)[:200]}", "_audio": b""}
                    names = ("mehmet",) if kind == "P" else ("ayşe", "ayse", "aysha", "aisha")
                    reply = r.get("reply", "").lower()
                    r["name_used"] = any(nm in reply for nm in names)
                    if r["_audio"]:
                        save_wav(OUT_DIR / f"reply_{short}_{kind}_{trial}.wav", r["_audio"])
                    rec = {"ts": round(time.time(), 1), "model": model, "kind": kind, "trial": trial,
                           **{k: v for k, v in r.items() if not k.startswith("_")}}
                    log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print(json.dumps(rec, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))

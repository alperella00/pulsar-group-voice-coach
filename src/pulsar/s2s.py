"""S2S istemcisi: Gemini 3.8 Live (MIMARI §5.9, K5, K17).

Bağlantı açık kalıyor; turu biz yönetiyoruz (otomatik tur tespiti kapalı):
  activity_start → tur sesi (16 kHz PCM16, 100 ms parçalar) → COACH NOTE (metin) → activity_end
Cevap 24 kHz PCM16 parçalar halinde geliyor; ayrı bir alıcı görev sürekli dinliyor.

session.receive() bir cevap bitince (turn_complete) duruyor; o yüzden alıcı onu döngü içinde tekrar çağırıyor.
"""
import asyncio
import os
import time
from typing import Awaitable, Callable

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL, API_VERSION = "gemini-3.8-live", "v1beta"
OUT_SR = 24000


class GeminiLive:
    def __init__(self, system: str, on_audio: Callable[[bytes], None],
                 on_done: Callable[[str], Awaitable[None]], on_event: Callable[..., None]):
        load_dotenv(".env")
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"api_version": API_VERSION})
        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=system,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)),
            output_audio_transcription=types.AudioTranscriptionConfig(),  # cevabın metni (soru ile mi bitti?)
        )
        self.on_audio, self.on_done, self.on_event = on_audio, on_done, on_event
        self._cm = self.session = self._rx = None
        self.t_sent: float | None = None
        self._first = True
        self._text: list[str] = []

    async def __aenter__(self):
        self._cm = self.client.aio.live.connect(model=MODEL, config=self.config)
        self.session = await self._cm.__aenter__()
        self._rx = asyncio.create_task(self._receiver())
        return self

    async def __aexit__(self, *exc):
        self._rx.cancel()
        await self._cm.__aexit__(*exc)

    async def send_turn(self, audio: np.ndarray, note: str) -> None:
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        s = self.session
        await s.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(pcm), 3200):  # 3200 byte = 1600 örnek = 100 ms
            await s.send_realtime_input(audio=types.Blob(data=pcm[i:i + 3200], mime_type="audio/pcm;rate=16000"))
        await s.send_realtime_input(text=note)
        await s.send_realtime_input(activity_end=types.ActivityEnd())
        self.t_sent, self._first, self._text = time.perf_counter(), True, []

    async def _receiver(self):
        while True:
            async for msg in self.session.receive():
                if msg.data:
                    if self._first and self.t_sent:
                        self._first = False
                        self.on_event("first_audio", ttfb_ms=round((time.perf_counter() - self.t_sent) * 1000, 1))
                    self.on_audio(msg.data)
                sc = msg.server_content
                if sc and sc.output_transcription and sc.output_transcription.text:
                    self._text.append(sc.output_transcription.text)
                if sc and sc.turn_complete:
                    await self.on_done("".join(self._text).strip())
                if msg.go_away:
                    self.on_event("go_away", time_left=str(msg.go_away.time_left))

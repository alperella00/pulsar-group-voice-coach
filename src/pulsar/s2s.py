"""S2S istemcisi: Gemini 3.8 Live (MIMARI §5.9, K5, K17).

Bağlantı açık kalıyor; turu biz yönetiyoruz (otomatik tur tespiti kapalı):
  activity_start → tur sesi (16 kHz PCM16, 100 ms parçalar) → COACH NOTE (metin) → activity_end
Cevap 24 kHz PCM16 parçalar halinde geliyor; ayrı bir alıcı görev sürekli dinliyor.

session.receive() bir cevap bitince (turn_complete) duruyor; o yüzden alıcı onu döngü içinde tekrar çağırıyor.

Proaktif soru: ses yok, sadece metin talimatı (send_client_content, turn_complete=True); ilk ses ~0,6 sn (K17 testi).
Söz kesme: Pulsar cevap üretirken yeni activity_start gelirse Gemini eski üretimi keser ("interrupted").
O ana kadar eski cevaptan gelen parçalar çöpe atılıyor (dropping) ve eski cevap için on_done çağrılmıyor.
Bağlantı: sunucu uzun süre bir şey gönderilmeyince bağlantıyı kapatıyor ("client inactivity", AMI testinde ~3 dk);
gönderimden önce bağlantı kapalıysa yeniden bağlanılıyor (_ensure). Bedeli: uzun sessizlik sonrası ilk cevaba bağlanma süresi.
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
        self.generating = False   # model şu an cevap üretiyor mu
        self.dropping = False     # söz kesildi: eski cevabın kalan parçalarını at

    async def __aenter__(self):
        await self._connect()
        return self

    async def __aexit__(self, *exc):
        await self._close()

    async def _connect(self):
        self._cm = self.client.aio.live.connect(model=MODEL, config=self.config)
        self.session = await self._cm.__aenter__()
        self._rx = asyncio.create_task(self._receiver())
        self.closed = False

    async def _close(self):
        if self._rx:
            self._rx.cancel()
        try:
            await self._cm.__aexit__(None, None, None)
        except Exception:
            pass

    async def _ensure(self):
        if getattr(self, "closed", True):
            t0 = time.perf_counter()
            await self._close()
            await self._connect()
            self.generating = self.dropping = False
            self.on_event("reconnect", ms=round((time.perf_counter() - t0) * 1000, 1))

    async def send_turn(self, audio: np.ndarray, note: str) -> None:
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        await self._ensure()
        s = self.session
        await s.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(pcm), 3200):  # 3200 byte = 1600 örnek = 100 ms
            await s.send_realtime_input(audio=types.Blob(data=pcm[i:i + 3200], mime_type="audio/pcm;rate=16000"))
        await s.send_realtime_input(text=note)
        await s.send_realtime_input(activity_end=types.ActivityEnd())
        self.t_sent, self._first, self._text, self.generating = time.perf_counter(), True, [], True

    async def send_text(self, instruction: str) -> None:
        """Sesli tur olmadan sadece metin talimatıyla cevap (proaktif soru)."""
        await self._ensure()
        await self.session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=instruction)]), turn_complete=True)
        self.t_sent, self._first, self._text, self.generating = time.perf_counter(), True, [], True

    def interrupt(self) -> None:
        """Söz kesme: üretim sürüyorsa eski cevabın kalanını atmaya başla (yeni tur hemen arkasından gönderilir)."""
        if self.generating:
            self.dropping = True
            self.generating = False

    async def _receiver(self):
        try:
            await self._receive_loop()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # bağlantı koptu (ör. inactivity): bir sonraki gönderimde yeniden bağlan
            self.closed = True
            self.on_event("connection_closed", reason=f"{type(e).__name__}: {str(e)[:120]}")

    async def _receive_loop(self):
        while True:
            async for msg in self.session.receive():
                sc = msg.server_content
                if self.dropping:
                    if sc and (sc.interrupted or sc.turn_complete):
                        self.dropping = False
                        self.on_event("interrupted_old")
                    continue
                if msg.data:
                    if self._first and self.t_sent:
                        self._first = False
                        self.on_event("first_audio", ttfb_ms=round((time.perf_counter() - self.t_sent) * 1000, 1))
                    self.on_audio(msg.data)
                if sc and sc.output_transcription and sc.output_transcription.text:
                    self._text.append(sc.output_transcription.text)
                if sc and sc.turn_complete:
                    self.generating = False
                    asyncio.create_task(self.on_done("".join(self._text).strip()))
                if msg.go_away:
                    self.on_event("go_away", time_left=str(msg.go_away.time_left))

"""Gemini API'de bu key ile erişilebilen canlı (Live / native audio) modelleri listeler."""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

for m in client.models.list():
    name = m.name or ""
    actions = m.supported_actions or []
    if "live" in name or "native-audio" in name or "bidiGenerateContent" in actions:
        print(f"{name:60s} actions={actions}")

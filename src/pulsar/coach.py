"""COACH NOTE: Gemini'ye turla birlikte giden "kime, nasıl cevap ver" notu (MIMARI §5.9, K17).

Model kimin konuştuğunu sesten tahmin etmiyor; sadece bu nottan öğreniyor. Gemini sadece Pulsar'a söylenen turları
duyduğu için, grubun kendi arasında konuştuklarını (ASR metni, sadece bellekte) da kısaca nota ekliyoruz.
Prosodi ve CEFR geldiğinde ton satırı buraya eklenecek (K6).
"""
from collections import deque

SYSTEM = (
    "You are Pulsar, a friendly English speaking coach who joins a small online group conversation. "
    "Several people share one audio stream. Only the COACH NOTE tells you who is speaking; never guess the speaker "
    "from the voice. Address the speaker by the name in the COACH NOTE. Keep replies short: at most 2 sentences, "
    "simple and natural spoken English. Ask a short follow-up question when it fits."
)


class Coach:
    def __init__(self, recent: int = 4):
        self.recent: deque[tuple[str, str]] = deque(maxlen=recent)  # (kim, ne dedi) son konuşmalar

    def heard(self, who: str | None, text: str) -> None:
        if text:
            self.recent.append((who or "someone", text))

    def note(self, speaker: str | None) -> str:
        if speaker is None:
            body = ("Speaker: unknown (could not tell who is speaking). Do not guess a name. "
                    "Politely ask who asked, e.g. 'Sorry, who asked that?', then answer briefly.")
        else:
            body = (f"Speaker: {speaker}. Reply to {speaker} by name. At most 2 short sentences, warm, "
                    f"end with an easy question if it fits.")
        ctx = ""
        if self.recent:
            ctx = " Recent group talk: " + " | ".join(f"{w}: {t}" for w, t in self.recent)
        return f"[COACH NOTE] {body}{ctx}"

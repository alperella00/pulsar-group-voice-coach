"""COACH NOTE: Gemini'ye turla birlikte giden "kime, nasıl cevap ver" notu (MIMARI §5.9, K17).

Model kimin konuştuğunu sesten tahmin etmiyor; sadece bu nottan öğreniyor. Gemini sadece Pulsar'a söylenen turları
duyduğu için, grubun kendi arasında konuştuklarını (ASR metni, sadece bellekte) da kısaca nota ekliyoruz.
Ton satırı prosodi durumundan kurallarla seçiliyor (K6; her turda LLM yok). Gemini'de hız parametresi yok,
hız doğal dil talimatıyla etkileniyor; işe yarayıp yaramadığı scripts/eval_tone.py ile ölçülüyor (M6).
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

    @staticmethod
    def tone(state: str | None, speaker: str | None) -> str:
        who = speaker or "them"
        if state == "struggling":
            return (f" Tone: {who} is speaking much slower than usual and pausing a lot, maybe struggling. "
                    f"Speak about 25% slower than normal, with natural pauses between sentences. Use very short, "
                    f"simple sentences. Start with a short encouraging acknowledgement, then ask one easy question.")
        if state == "slightly_slow":
            return " Tone: use slightly shorter and simpler sentences than usual."
        return ""

    def note(self, speaker: str | None, state: str | None = None) -> str:
        if speaker is None:
            body = ("Speaker: unknown (could not tell who is speaking). Do not guess a name. "
                    "Politely ask who asked, e.g. 'Sorry, who asked that?', then answer briefly.")
        else:
            body = (f"Speaker: {speaker}. Reply to {speaker} by name. At most 2 short sentences, warm, "
                    f"end with an easy question if it fits.")
        ctx = ""
        if self.recent:
            ctx = " Recent group talk: " + " | ".join(f"{w}: {t}" for w, t in self.recent)
        return f"[COACH NOTE] {body}{self.tone(state, speaker)}{ctx}"

    def proactive(self, name: str) -> str:
        ctx = " | ".join(f"{w}: {t[:120]}" for w, t in self.recent) or "small talk"
        return (f"[COACH NOTE] {name} has been quiet for a while. Recent group talk: {ctx}. "
                f"Ask {name} one short, friendly, easy question related to what the group is talking about. "
                f"Use {name}'s name. One sentence only.")

"""Hitap tespiti: bu tur Pulsar'a mı söylendi? (MIMARI §5.3, K3, K21)

Kurallar sırayla; ilk tutan kazanır. Belirsizse Pulsar susar (sohbeti gereksiz bölmek kötü bir deneyim).

  0. Başka bir katılımcıya hitap ("Mehmet, what do you think?")  → HAYIR (takip penceresi açık olsa bile)
  1. "Pulsar" ya da 1 harf farkla benzeri geçiyor ("Pussar")      → EVET
     · Levenshtein ≤ 1 (≤ 2 "pulse"u da yakalıyordu, reports/addressing_asr.md)
     · çoğul hali ("pulsars") sayılmıyor: gök cismi olarak bahsediliyor, hitap değil
  2. Takip penceresi: Pulsar az önce bu kişiye cevap verdi; soruyla bitirdiyse 8 sn, bitirmediyse 4 sn → EVET
  3. Tur bir soru ve son 30 sn içinde Pulsar'a hitap edilmiş     → EVET
  Hiçbiri değilse                                                  → HAYIR (sadece kayıt)
"""
import re
from dataclasses import dataclass

WH = {"what", "why", "how", "when", "where", "who", "which", "whose", "whom"}
AUX = {"do", "does", "did", "can", "could", "would", "will", "should", "is", "are", "was", "were", "have", "has",
       "may", "might", "shall", "am"}


def lev(a: str, b: str) -> int:
    """Levenshtein: a'yı b'ye çevirmek için gereken en az harf ekleme/silme/değiştirme sayısı."""
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def is_question(text: str) -> bool:
    w = words(text)
    return text.rstrip().endswith("?") or bool(w and (w[0] in WH or w[0] in AUX))


@dataclass
class Decision:
    addressed: bool
    rule: str      # "other_person" | "name" | "follow_up" | "question" | "none"
    detail: str = ""


class Addressing:
    def __init__(self, participants: list[str], name: str = "pulsar", max_lev: int = 1,
                 follow_q_s: float = 8.0, follow_s: float = 4.0, recent_s: float = 30.0):
        self.name, self.max_lev = name.lower(), max_lev
        self.participants = {p.lower() for p in participants}
        self.follow_q_s, self.follow_s, self.recent_s = follow_q_s, follow_s, recent_s
        self.reply: tuple[str, float, bool] | None = None  # (kime, cevabın bittiği an, soruyla mı bitti)
        self.last_addressed_t: float | None = None

    def name_match(self, text: str) -> str | None:
        for w in words(text):
            if lev(w, self.name) <= self.max_lev:
                plural = w.endswith("s") and len(w) > len(self.name) and lev(w[:-1], self.name) <= self.max_lev
                if not plural:
                    return w
        return None

    def other_person(self, text: str, speaker: str | None) -> str | None:
        """Cümle başka bir katılımcının ismiyle başlıyor ya da bitiyor mu? (hitap genelde başta ya da sonda olur)"""
        w = words(text)
        others = self.participants - {(speaker or "").lower()}
        for cand in (w[:1] + w[-1:]):
            if cand in others:
                return cand
        return None

    def decide(self, text: str, speaker: str | None, t: float) -> Decision:
        """t: turun başladığı an (sn)."""
        if (p := self.other_person(text, speaker)) and not self.name_match(text):
            return Decision(False, "other_person", p)
        if m := self.name_match(text):
            return self._yes("name", m, t)
        if self.reply and speaker and speaker == self.reply[0]:
            who, end, asked = self.reply
            window = self.follow_q_s if asked else self.follow_s
            if 0 <= t - end <= window:
                return self._yes("follow_up", f"{t - end:.1f} sn < {window:.0f} sn", t)
        if is_question(text) and self.last_addressed_t is not None and t - self.last_addressed_t <= self.recent_s:
            return self._yes("question", f"son hitaptan {t - self.last_addressed_t:.1f} sn sonra", t)
        return Decision(False, "none")

    def on_reply(self, to: str | None, end_t: float, ended_with_question: bool) -> None:
        """Pulsar cevabını bitirince çağrılır: takip penceresi açılır."""
        self.reply = (to, end_t, ended_with_question)

    def _yes(self, rule: str, detail: str, t: float) -> Decision:
        self.last_addressed_t = t
        return Decision(True, rule, detail)

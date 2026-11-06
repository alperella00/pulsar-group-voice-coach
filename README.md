# Pulsar — a speech-to-speech coach for group conversation practice

> Work in progress (November 2026).

Pulsar joins a small group conversation (3–4 people, one mixed audio stream) and acts as an English speaking coach:

- **Who is speaking?** Speaker embeddings (WeSpeaker ResNet34) matched against a short enrollment of each participant.
- **How are they speaking?** Prosody — pitch, energy, speech rate, pauses, mean length of run — compared to each
  person's *own* baseline (z-scores).
- **Reply accordingly.** Only turns addressed to Pulsar are sent to a speech-to-speech model (Gemini Live, manual turn
  control) together with a short coach note: who spoke, their level, and how to adapt (pace, sentence length, warmth).

It also tracks each person's share of talking time and invites quiet participants into the conversation.

## First findings (Nov 6, 2026)

**Speaker identification gets harder as the group grows and turns get shorter** (LibriSpeech test-clean, 40 speakers,
25 s enrollment each). For the demo's 3-person group, 2-second turns are identified correctly **95%** of the time;
with a tuned threshold the system says *"who asked that?"* on 8% of turns and uses the **wrong name on 1.4%**.
Weak spot: an *unenrolled* stranger gets matched to someone in a 3-person group ~30% of the time — score
normalization is next.

![Speaker ID accuracy vs group size](reports/figures/speaker_id_vs_group_size.png)

**Gemini 3.8 Live with manual turn control** answered 9/9 test turns and always used the coach note (the speaker's name
was only in the note, never in the audio). Time to first audio after closing the turn: ~1.6 s for an audio turn,
~0.6 s for a text-only prompt.

Full results, tables and charts (Turkish): [`reports/README.md`](reports/README.md).

**Next steps beyond the demo:** per-learner long-term memory (RAG over session summaries — recurring mistakes, vocabulary,
fluency trends — retrieved once per session, not per turn), group-scoped voice-print storage, and multi-room serving.

Design docs (Turkish for now): [`docs/DURUM.md`](docs/DURUM.md) (status & next steps), [`docs/MIMARI.md`](docs/MIMARI.md) (architecture),
[`docs/KARARLAR.md`](docs/KARARLAR.md) (decisions), [`docs/ARASTIRMA.md`](docs/ARASTIRMA.md) (research notes & sources).

# Pulsar — a speech-to-speech coach for group conversation practice

> Work in progress (November 2026).

Pulsar joins a small group conversation (3–4 people, one mixed audio stream) and acts as an English speaking coach:

- **Who is speaking?** Speaker embeddings (WeSpeaker ResNet34) matched against a short enrollment of each participant.
- **How are they speaking?** Prosody — pitch, energy, speech rate, pauses, mean length of run — compared to each
  person's *own* baseline (z-scores).
- **Reply accordingly.** Only turns addressed to Pulsar are sent to a speech-to-speech model (Gemini Live, manual turn
  control) together with a short coach note: who spoke, their level, and how to adapt (pace, sentence length, warmth).

It also tracks each person's share of talking time and invites quiet participants into the conversation.

**Next steps beyond the demo:** per-learner long-term memory (RAG over session summaries — recurring mistakes, vocabulary,
fluency trends — retrieved once per session, not per turn), group-scoped voice-print storage, and multi-room serving.

Design docs (Turkish for now): [`docs/MIMARI.md`](docs/MIMARI.md) (architecture),
[`docs/KARARLAR.md`](docs/KARARLAR.md) (decisions), [`docs/ARASTIRMA.md`](docs/ARASTIRMA.md) (research notes & sources).

---
name: captions
description: Add word-level timed subtitles to a Cutroom cut using ASR (Whisper large-v3-turbo via MLX, ElevenLabs Scribe fallback), styled per aspect ratio and burned in. Use after every final assembly.
---

# Word-level captions

`captions(project_id, cut_path)` transcribes the cut's audio with word timestamps, groups words into readable lines,
writes `.srt` and a styled `.ass`, and burns the captions into a new mp4 with the current word highlighted as it is
spoken.

## What good captions look like

- Two lines at most, about 32 characters per line in 16:9 and 22 in 9:16 and 1:1.
- Line breaks fall at phrase boundaries, never between an article and its noun.
- Captions sit inside the safe area: bottom-centred in 16:9; lower third, above platform UI, in 9:16.
- Each caption stays on screen at least 0.8 s.

## Checking them

The transcript the tool returns is also the best check on the voiceover. Compare it with the plan's narration:
a misheard word usually means the TTS mispronounced it. Fix pronunciation by rewriting the word (for example,
spelling out an acronym as it should be said) and re-recording that line, then caption again.

Proper nouns the ASR gets wrong can be corrected by passing `corrections={"wrong": "right"}`.

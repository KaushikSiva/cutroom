---
name: voice-emotion
description: Direct an emotive, human-sounding voiceover with Gemini 3.8 TTS through Cutroom's voiceover tool — per-line style directions, inline vocal tags, voice choice and pacing. Use whenever recording or re-recording narration.
---

# Voice direction for Gemini TTS

Cutroom's `voiceover(project_id, segments=[{shot_id, text, direction}])` calls Gemini 3.8 Flash TTS
(`gemini-3.8-flash-tts`). The API has two separate controls, and mixing them up is the most common mistake:

1. **`direction` → style metadata (whole line).** Sustained delivery: emotion, pace, energy, attitude. The API
   receives it as `speech_metadata.style`. Examples: "warm and measured, like a professor who loves this subject",
   "hushed, reverent", "speaking a little faster, excited by the discovery", "dry, faintly amused".
2. **Inline tags in `text` (a moment).** The text is read **verbatim**, so stage directions such as "(sadly)" would be
   spoken aloud. Only use the supported angle-bracket tags inside text:
   `<short pause>`, `<long pause>`, `<breath>`, `<sigh>`, `<chuckle>`, `<laugh>`, `<gasp>`, `<throat-clearing>`.

## How to direct a line

Describe the feeling and the intention, not the acoustics. "Gently correcting a common misunderstanding" works better
than "lower pitch". Change the direction from line to line as the content changes: curiosity at a question, gravity at
a consequence, warmth at a human story, a lift at a turn in the argument. A film read in one tone sounds synthetic.

Use pauses as a lecturer does: a `<short pause>` before the key idea of a sentence, a `<long pause>` after a line
that needs to land, a `<breath>` before a long sentence. One or two tags per line at most.

| Moment | direction | text example |
|---|---|---|
| Cold open | "quiet, intrigued, unhurried, drawing the listener in" | `In a converted warehouse outside Dallas, <short pause> the air hums with a sound that did not exist a decade ago.` |
| Explaining | "clear and patient, like a favourite lecturer at the whiteboard" | `The reason is simpler than it sounds, <short pause> and it begins with electricity.` |
| A consequence | "grave, slower, letting the weight settle" | `For the companies that bet wrong, <breath> there was no second chance. <long pause>` |
| A light moment | "dry, faintly amused" | `It was, <chuckle> not the last time someone would call it a bubble.` |

## Voice

Default narrator: **Sulafat** (warm). Alternatives: Algieba (smooth), Kore (firm), Achernar (soft), Enceladus
(breathy, intimate), Puck (upbeat, for lighter films). Keep one narrator per film; use a second voice only for quoted
speech.

## Pacing check

`voiceover` returns each segment's duration. If a line runs longer than its shot, first tighten the wording; only then
lengthen the shot in the plan. Never ask for faster speech to cram text in, because it ruins the professor's cadence.

If the TTS provider is unavailable the tool falls back to the macOS system voice; say so in your summary, since the
emotion directions won't apply to that fallback.

---
name: assemble-otio
description: Assemble a Cutroom film as an OpenTimelineIO timeline and render it with ffmpeg — animatic and final modes, track layout, transitions, audio ducking and loudness. Use whenever building an animatic or a cut.
---

# Assembly with OpenTimelineIO

`assemble(project_id, mode)` builds an OpenTimelineIO timeline from the saved plan and every asset produced so far,
writes it as `cuts/<round>.otio`, and renders it with ffmpeg. The `.otio` file opens in Resolve, Premiere or Avid, so
a human editor can take over at any point.

## Tracks

| Track | Contents |
|---|---|
| V1 | One clip per shot in plan order: generated shot, footage section or full-frame graphic |
| V2 | Overlays with transparency: lower thirds, callouts |
| A1 | Voiceover, one clip per shot, aligned to the shot start |
| A2 | Music, ducked under the voice and faded in and out |

## Modes

- **animatic**: keyframe stills with a gentle push-in, each held for its planned duration, with the voiceover (or a
  scratch voice) and the shot id and timecode burned in. It is cheap and quick; use it to fix timing and order before
  generating video.
- **final**: real shots, clips and graphics, normalised to the project resolution and 30 fps, cropped to the aspect
  ratio, with music ducked under the voice and the mix normalised to −16 LUFS.

## Editing rules the tool follows, which you control through the plan

- Each shot lasts its `duration_s`. If its voice line is longer, the shot is extended to the line plus 0.4 s; fix the
  plan instead of relying on this.
- Cuts are straight by default; set `"transition": "dissolve"` on a shot to dissolve into it (use for time jumps and
  chapter changes, sparingly).
- Footage plays at its natural speed; a section shorter than the shot is slowed slightly rather than frozen.

After every final assembly, run `captions` and then `critique` before deciding what to change.

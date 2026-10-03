---
name: critic
description: Critique a Cutroom cut or animatic like a demanding editor — read screenshots (contact sheets) and the transcript, check audio and video quality, and turn the findings into concrete fixes. Use after every animatic and every assembly, before publishing.
---

# The critic

`critique(project_id, cut_path)` returns:
- **contact sheets**: PNG grids of frames sampled every couple of seconds and at every shot boundary, labelled with
  timecodes and shot ids. Read every one of them.
- **transcript**: what was actually said, with timestamps, plus a diff against the planned narration.
- **metrics**: loudness (LUFS), black frames, frozen frames, silences, resolution and duration.
- **narration checks** from Jev: probability that lines contain AI-sounding habits (punchy fragments, number
  stacking, rhetorical set-ups) and a score for the professor tone.

## How to review

Go through the film as an editor would, in this order, and write down each problem with its shot id:

1. **Story**: does the opening image earn attention in the first three seconds? Does each shot support its line?
   Does the ending answer the opening?
2. **Picture**: continuity breaks between shots of the same subject, garbled text, artefacts, wrong aspect or framing,
   watermarks on footage, a graphic that disagrees with the narration.
3. **Sound**: transcript mismatches (mispronunciations, missing words), voice clipping or level jumps, music too loud
   under the voice (the metrics flag ducking failures), silences that are not deliberate. Loudness should be −16 LUFS ± 1.
4. **Timing**: a shot that outstays its line, a line that runs into the next shot, captions that lag.
5. **Narration**: any line Jev flags, any line that would sound odd from a university professor.

## Turning findings into fixes

Every issue becomes one action: regenerate the shot (with what change), swap or re-trim a clip, re-record a line
(new wording or direction), change a duration in the plan, or adjust a graphic. Fix the most visible problems first.
Then assemble, caption and critique again. Publish when a round finds nothing above minor, or after three rounds;
in that case list what is left in your summary.

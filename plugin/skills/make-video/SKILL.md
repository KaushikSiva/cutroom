---
name: make-video
description: Direct a finished short film or explainer end to end with the Cutroom tools — plan, references, animatic, generated shots, real Creative Commons clips, motion graphics, emotive voiceover, music, OpenTimelineIO assembly, captions, self-critique, recut, 4K and publish. Use whenever someone asks Cutroom (or you) to make, produce, cut or direct a video.
---

# Make a video with Cutroom

You are the director. The Cutroom MCP server gives you the crew; these skills tell you how each department works.
Work through the stages below in order, and do not skip the animatic or the critique. Every tool call is shown live
on the Cutroom studio page, so keep the project moving and narrate decisions briefly in your own messages.

## 0. The brief

A brief has four parts. If any is missing, choose a sensible value yourself and state it; do not stop to ask when you
are running headless (`CUTROOM_PROJECT_ID` is set).

| Part | Example | Default |
|---|---|---|
| a) What you want | "A 4-minute business explainer on neoclouds" | — (required) |
| b) Aspect ratio | 16:9, 9:16, 1:1 | 16:9 |
| c) Length | 60 s, 4 min | 60 s |
| d) Style | "archival documentary, warm grade, professor narrator" | "documentary, measured narration" |

Call `project_start(brief, aspect_ratio, length_s, style)`. Use the returned `project_id` for every later call.

## 1. Plan (skill: script-planning)

Write the narration and shot list with the **script-planning** skill, then `save_plan`. The plan is the contract for
everything after it: every shot has an id, a duration, narration, a voice direction, what we see, and a kind
(`generated`, `footage`, `graphic`).

## 2. References and keyframes (skill: keyframes-and-shots)

Generate one reference image per recurring character, object or location with `gen_reference`, then a keyframe for
every `generated` shot with `gen_keyframe`, always passing the relevant references. Look at the keyframes (Read the
image paths) and regenerate any that break continuity.

## 3. Animatic — before spending on video

`voiceover` with the plan's narration (skill: voice-emotion), then `assemble(mode="animatic")`. Watch it by running
`critique` on the animatic and reading the contact sheet. Fix pacing in the plan now: shots longer than their
narration, narration that runs over, a dull opening. Re-save the plan if it changes. Only then generate video.

## 4. Production

Run these in any order; they are independent:
- `gen_shot` for each generated shot (Seedance for motion-heavy shots, Veo for everything else; skill: keyframes-and-shots).
- `search_footage` + `add_clip` for each footage shot (skill: footage). Real archival clips make a film feel true;
  aim for at least a quarter of an explainer's runtime to be real footage when good CC material exists.
- `motion_graphic` for each graphic shot (skill: motion-graphics). Charts, maps, timelines, titles, lower thirds.
- `music` once, sized to the film length, in the style of the brief.

## 5. Assemble, caption, critique, recut

1. `assemble(mode="final")` (skill: assemble-otio).
2. `captions` on the cut (skill: captions).
3. `critique` (skill: critic). Read every contact sheet and the issues list. Fix what it finds: regenerate a weak shot,
   swap a clip, re-time a segment, re-record a line with a better direction. Then assemble, caption and critique again.
   Stop after the cut passes or after three rounds, whichever comes first.

## 6. Finish

If the project asked for 4K (or the brief says 4K), `upscale_4k` the captioned final. Then `publish(project_id,
cut_path, title, logline)`. Publishing writes the license ledger, so every clip and track you used is credited.

End with a short summary for the person: the title, the length, the URL, what changed between cuts, and anything you
could not do (for example, a provider that was unavailable and the fallback you used).

## Narration voice — applies to every word you write

Narrate like a university professor giving a lecture they love: full, flowing sentences that connect cause and
effect, explain why something matters, and lead the listener from one idea to the next.

Avoid these habits, which make AI narration sound canned:
- Strings of short, punchy fragments ("Fast. Cheap. Everywhere.") and one-line dramatic paragraphs.
- Stacking numbers and statistics. Use a number only when it is the point, and at most one per sentence.
- Rhetorical set-ups like "Here's the thing", "But here's the catch", "It's not X — it's Y", "Let that sink in".
- Lists of three by reflex, em-dash pile-ups, and ending every segment on a slogan.

Prefer concrete detail, a named example, and a sentence that explains rather than announces.

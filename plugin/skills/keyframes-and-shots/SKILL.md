---
name: keyframes-and-shots
description: Generate consistent reference images, keyframes and video shots for Cutroom through OpenRouter — GPT 2.5 Image (Sunburst) for stills, Seedance 2.5 for motion shots and Veo 3.1 for the rest. Use for every `generated` shot.
---

# References, keyframes and generated shots

Generation is the most expensive and least predictable part of the film, so it always runs in this order:
**references → keyframes → animatic → video**. Never generate video for a shot whose keyframe you have not looked at.

## 1. References (consistency anchors)

`gen_reference(project_id, name, prompt)` for every recurring character, object, vehicle or location. Write each
reference prompt as a neutral, well-lit, front-facing description with the details that must stay the same:
clothing, colours, materials, era, distinguishing features. These images are passed to every later generation
that shows that subject, which is what keeps a character recognisable from shot to shot.

## 2. Keyframes (GPT 2.5 Image "Sunburst")

`gen_keyframe(project_id, shot_id, prompt, refs=[names])`. A keyframe is the first frame of the shot. Write prompts like
a cinematographer: subject and action, framing (wide, medium, close), lens feel, lighting, time of day, palette, and
the film's style words from the brief. Keep the palette and grade consistent across the film by repeating the same
style phrase in every prompt.

Read every keyframe image. Regenerate when a reference is not respected, text in the image is garbled, the framing
doesn't support the narration, or the aspect ratio is wrong.

## 3. Video (after the animatic)

`gen_shot(project_id, shot_id, prompt, keyframe, motion, duration_s)`:
- `motion: true` → **Seedance 2.5**. It handles strong motion best: camera moves, people walking, vehicles, crowds,
  anything that travels across the frame.
- `motion: false` → **Veo 3.1**. Best for atmosphere, subtle movement, faces and talking, light changes.

The video prompt describes only what changes over the shot: "slow dolly forward; operator turns toward camera; steam
rises". The keyframe already fixes how it looks. Keep shots to 4–8 s; generate longer moments as two shots.

If a provider is unavailable the tool falls back to a camera move over the keyframe (a Ken Burns push or pan). That is
fine for a few shots; mention it in your summary.

Jev (TypeSafe) scores which engine each shot should use when the plan doesn't say; follow its routing unless you have
a reason not to.

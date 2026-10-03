---
name: script-planning
description: Plan a Cutroom film — structure, narration script and shot list with timings, voice directions and visual kinds — before any generation. Use at the start of every video, and again when the animatic or critique shows the structure needs to change.
---

# Script and shot planning

## Shape the film first

Pick a structure that fits the length before writing a word:

| Length | Structure |
|---|---|
| ≤ 60 s | Hook (one striking image and a question) → one idea developed → a closing thought that answers the hook |
| 1–3 min | Hook → context → two or three developments, each with its own visual world → resolution |
| 3–5 min | Cold open → title → chapters (with chapter cards) → synthesis → closing image that echoes the open |

Budget narration at about **2.3 words per second** (a professor's measured pace). A 60 s film holds roughly 130
words; a 4-minute film roughly 550. Leave 1–2 s without narration at the open, at chapter changes and at the end,
so music and images can breathe.

### Tribute and montage films

For a montage of iconic moments (a national history, a career, a company's story), the archival sound carries the
film and the narrator only bridges. Plan roughly a third of the runtime as original sound (`keep_audio` shots: the
speech, the famous line, the crowd), and keep narration to short connective passages between them, still in the
professor's full sentences. Open and close on the same image (a founding document, a first photograph) so the film
reads as one arc, and move through time in order with a slug on every real shot.

## Write the narration

Follow the narration rules in the make-video skill: a university professor's voice, full connected sentences, few
numbers, no punchy fragments or rhetorical set-ups. Read each paragraph back and ask whether a thoughtful lecturer
would say it aloud in this way. Every sentence should either show the viewer something or explain why it matters.

## Break it into shots

One shot per visual idea, usually 3–8 s. Each narration sentence or clause gets a shot whose image supports it. Vary
the kinds so the film has rhythm:

| kind | Use for | Notes |
|---|---|---|
| `footage` | Real places, people, history, anything where truth matters | Needs a `youtube_query`; Creative Commons only |
| `generated` | Scenes that can't be filmed: the past, the abstract, the future, a recurring character | Set `motion: true` for camera moves or action (routes to Seedance) |
| `graphic` | Numbers, comparisons, maps, timelines, titles, definitions | Set `engine` (see motion-graphics) |

Open with the strongest image, not a title card. Put a title card after the cold open on films over 90 s. Use a lower
third the first time a person or place is named.

## Voice directions

Give every shot a `direction` for the voice (see voice-emotion): the emotional colour and pace of that line, for
example "curious, leaning in, slight smile" or "grave and slow, as if recounting a loss". Directions should change
with the content; a film read in one tone sounds synthetic.

## Plan format

Save with `save_plan(project_id, plan)`:

```json
{
  "title": "The Neocloud Gamble",
  "logline": "How a handful of GPU landlords became the most important companies nobody has heard of.",
  "aspect_ratio": "16:9", "length_s": 240, "style": "archival documentary, warm grade, professor narrator",
  "references": [{"name": "datacenter", "prompt": "vast dim data hall, rows of GPU racks with blue status lights, haze, wide lens"}],
  "shots": [
    {"id": "s01", "kind": "generated", "duration_s": 6, "motion": true, "refs": ["datacenter"],
     "visual": "slow push down an aisle of humming GPU racks, haze catching the light",
     "narration": "In a converted warehouse outside Dallas, the air hums with a sound that did not exist a decade ago.",
     "direction": "quiet, intrigued, unhurried"},
    {"id": "s02", "kind": "graphic", "engine": "hyperframes", "duration_s": 5,
     "visual": "title card: The Neocloud Gamble", "narration": "", "direction": ""},
    {"id": "s03", "kind": "footage", "duration_s": 7, "youtube_query": "1960s mainframe computer room",
     "visual": "archival mainframe room, operators at consoles",
     "narration": "Computing has been rented out before, and the story of how it happened the first time explains much of what is happening now.",
     "direction": "warm, storytelling, slight rise of interest"}
  ]
}
```

The sum of `duration_s` must be within 5% of `length_s`. Check this before saving.

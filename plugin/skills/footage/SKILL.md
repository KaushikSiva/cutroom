---
name: footage
description: Find and cut real Creative Commons clips from YouTube into a Cutroom film with yt-dlp search — querying, judging candidates, choosing in/out points and keeping the license ledger. Use for every `footage` shot.
---

# Real footage from YouTube

`search_footage(project_id, query, n)` searches YouTube with yt-dlp (Creative Commons only, unless the studio is
configured with `CUTROOM_FOOTAGE_LICENSE=any`) and returns candidates with title, channel, duration, license and a relevance score from Jev. `add_clip(project_id, youtube_id,
start, end, shot_id)` downloads just that section and records it in the license ledger, which `publish` turns into
the film's credits.

## Searching

Search for what a camera would have filmed, not for the idea: "1960s mainframe computer room operators" rather than
"history of cloud computing". Add era and place words. Try two or three phrasings per shot and prefer:
- archival and public-institution channels (NASA, national archives, universities, museums, government agencies),
- footage without on-screen talking heads, logos, watermarks or burned-in subtitles,
- the highest resolution available.

Whatever the license, every clip you use is recorded with its source and license and credited when you publish.
Prefer the original broadcaster or archive's upload over re-uploads. If a search returns nothing usable, rephrase or
change the shot to `generated` or `graphic`.

## Choosing the moment

Watch before choosing: the tool's candidate list includes chapter and description text, and you can call
`critique` on a downloaded clip to see a contact sheet. Pick in/out points on a clean action: start just before
movement begins, end before a cut in the source. Keep clips 3–8 s. Avoid frames with text that contradicts your
narration.

## Rhythm

Alternate real footage with generated shots and graphics. Real footage is what makes an explainer feel true, so use it
for anything that actually happened or actually exists.

## Original sound and slugs

Some moments are only themselves with their own sound: a president's speech, a commentator's call, mission control
cheering, "That's one small step for man". For those shots set `"keep_audio": true` in the plan and leave that shot's
`narration` empty; the clip's own audio plays and the music ducks under it. Choose in/out points on the exact words,
with a few frames of breath either side. `"source_gain"` (default 1.0) adjusts a quiet recording.

Give every real-footage shot a `"slug"`: the documentary line in the lower-left corner naming where and when, in the
form `"Pearl Harbor · December 7, 1941"`. Use the date of the event, not of the upload.

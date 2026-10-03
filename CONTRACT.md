# Cutroom — build contract

Cutroom is a video studio for AI agents, driven by **Claude Code**. It ships as a Claude Code plugin (skills + an MCP
tools server). You brief it with a) what you want b) aspect ratio c) length d) style, and Claude Code plans the script,
builds reference images and an animatic, generates shots, pulls real Creative Commons clips, renders motion graphics,
records an emotive voiceover, scores music, assembles with OpenTimelineIO + ffmpeg, burns word-level captions,
critiques its own cut from screenshots + transcript, re-cuts, upscales to 4K and publishes.
Supabase holds projects, the live event feed, assets and the license ledger; the Vercel site shows the studio live,
the gallery, Stripe credits, and a remote MCP endpoint so other agents can order films. Jobs from the site / remote
agents run `claude -p` headless on this Mac with the same plugin.

Deadline: 17:30 PT today. Everything must work end to end; every provider call needs a working fallback.

## Layout

```
supabase/schema.sql                 accounts, projects, events, clips; bucket "media" (public); Realtime on projects+events
plugin/                             the Claude Code plugin (load with: claude --plugin-dir plugin)
  .claude-plugin/plugin.json
  .mcp.json                         stdio MCP server: python -m cutroom (cwd plugin/server)
  skills/<name>/SKILL.md            make-video, script-planning, voice-emotion, motion-graphics, keyframes-and-shots,
                                    footage, assemble-otio, captions, critic
  server/cutroom/                   Python MCP server (FastMCP, package `mcp`)
    __main__.py, server.py          tool registration
    db.py                           Supabase (service role): emit(pid, kind, message, data), update(pid, **f), upload(path, key)->url
    project.py                      project workspace: ~/workspace/cutroom/projects/<pid>/{refs,keyframes,shots,clips,gfx,audio,cuts}
    providers/openrouter.py         image gen (keyframes, refs), video gen (Veo 3.1, Seedance 2.5) — model ids from env, discovered via /api/v1/models
    providers/gemini_tts.py         Gemini TTS with style/emotion direction
    providers/elevenlabs.py         music generation (background), optional SFX
    providers/asr.py                word-level transcription (mlx-whisper local; ElevenLabs Scribe fallback)
    footage.py                      yt-dlp search (Creative Commons only) + section download
    motion/hyperframes.py           render(html_or_dir, out, w, h, fps, duration) -> {path}
    motion/manim_r.py               render(scene_code, scene_name, out, w, h, fps) -> {path}
    motion/motion_canvas.py         render(scene_tsx, out, w, h, fps, duration) -> {path}
    motion/blender.py               render(template, params, out, w, h, fps) -> {path}; templates in motion/blender_tpl/*.py
    assemble.py                     OTIO timeline (json) -> .otio -> ffmpeg render; animatic mode (stills + scratch VO)
    captions.py                     ASR words -> styled ASS subtitles -> burn in
    critic.py                       sample screenshots (contact sheet) + transcript + loudness/black/freeze checks -> report
    providers/jev.py                Jev (TypeSafe System One, `pip install typesafe-sdk`, TYPESAFE_API_KEY, model jev-latest):
                                    route_shot(shot)->Choice engine+confidence · rank_footage(shot, candidates)->Score each ·
                                    judge_narration(text)->Nouls/Score (claudisms, number-heavy, professor tone) — used by
                                    critic.py and footage.py; low confidence → leave the call to Claude
    upscale.py                      Real-ESRGAN 2x/4x via realesrgan-ncnn-vulkan (tools/realesrgan/)
worker/run.py                       polls Supabase for queued projects, runs `claude -p` headless with the plugin, streams to events
web/                                Next.js (App Router, TS, Tailwind, framer-motion) on Vercel
```

## Env (repo-root `.env`; the MCP server and worker load it with python-dotenv)
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL, ANTHROPIC_API_KEY (headless runs),
GEMINI_API_KEY, OPENROUTER_API_KEY, ELEVENLABS_API_KEY, TYPESAFE_API_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_CENTS,
NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY.
Model ids (override in .env; verify against provider model lists before use):
CUTROOM_IMAGE_MODEL (GPT 2.5 Image "Sunburst"), CUTROOM_VIDEO_MODEL_MOTION (Seedance 2.5 — motion shots),
CUTROOM_VIDEO_MODEL (Veo 3.1 — everything else), CUTROOM_TTS_MODEL (Gemini 3.8 TTS).

## MCP tools (all take project_id; every call emits events)
project_start(brief, aspect_ratio="16:9"|"9:16"|"1:1", length_s, style) -> {project_id, dir, width, height}
save_plan(project_id, plan)                         script/shot plan (shape below) -> stored in projects.script
gen_reference(project_id, name, prompt)             character/location reference image (consistency anchor)
gen_keyframe(project_id, shot_id, prompt, refs=[]) -> image path
render_animatic(project_id)                         keyframes + scratch VO on the plan timing -> mp4 (review before spending on video)
gen_shot(project_id, shot_id, prompt, keyframe, motion=bool, duration_s) -> video path  (motion → Seedance, else Veo)
search_footage(project_id, query, n) / add_clip(project_id, youtube_id, start, end, shot_id)
motion_graphic(project_id, shot_id, engine="hyperframes"|"manim"|"motion_canvas"|"blender", source|template, params)
voiceover(project_id, segments=[{shot_id, text, direction}]) -> per-segment wav + durations
music(project_id, prompt, length_s) -> wav (ducked under VO at assembly)
assemble(project_id, mode="animatic"|"final") -> {otio_path, mp4_path, url}
captions(project_id, cut_path) -> {srt, ass, burned_mp4}
critique(project_id, cut_path) -> {contact_sheet(s) png paths, transcript, issues: [..], metrics}
upscale_4k(project_id, cut_path) -> path
publish(project_id, cut_path, title, logline) -> {url}   uploads, writes credits ledger, status=done

## Plan shape (projects.script)
{ "title", "logline", "aspect_ratio", "length_s", "style",
  "references": [{"name","prompt","path?"}],
  "shots": [{ "id":"s01", "kind":"generated"|"footage"|"graphic", "duration_s", "narration", "direction" (voice emotion),
              "visual" (what we see), "motion": bool, "engine"? , "youtube_query"? , "refs": [names] }] }

## events.kind (rendered live by the web studio)
stage {stage, progress} · thought {} · tool {tool, input} · reference {name,url} · keyframe {shot_id,url} ·
animatic {url} · shot {shot_id,url,model} · clip {youtube_id,title,channel,license,thumb,start,end} ·
graphic {shot_id,engine,url} · voice {shot_id,url,duration} · music {url} · cut {round,url,duration} ·
captions {url} · critique {round, issues, contact_sheet_url} · upscale {url} · error {} · done {video_url,video_4k_url?}
Stages/progress: brief 2 · plan 8 · references 15 · animatic 25 · shots 45 · footage 50 · graphics 60 · voice 68 ·
music 72 · assemble 80 · captions 85 · critique 90 · recut 94 · upscale 97 · done 100.

## Web API (Next.js route handlers, service role on the server)
POST /api/projects {brief, aspect_ratio, length_s, style, want_4k}  auth: Supabase JWT or x-api-key → queued project
GET /api/projects/:id · POST /api/checkout · POST /api/stripe/webhook · GET /api/me
/api/mcp — remote MCP for other agents: make_video, get_status, get_credits, list_videos, buy_credits

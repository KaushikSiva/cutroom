"""Cutroom MCP server (stdio). Tools for planning, generating, cutting, captioning, critiquing and publishing a film.

Every tool writes progress to Supabase `events` so the web studio animates the work live. Blocking work runs in a
thread so Claude Code can call several tools in parallel (e.g. one gen_shot per shot).
"""
import concurrent.futures as cf
import inspect
import io
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import anyio

from . import assemble as asm
from . import captions as cap
from . import config, critic, db, footage, project
from .config import log
from .providers import elevenlabs, gemini_tts, jev, openrouter
from .util import duration, ffmpeg

from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = """Cutroom is a video studio. Start with project_start, save a plan, build references and keyframes,
review an animatic, then generate shots, footage, graphics, voice and music, assemble, caption, critique, recut, and
publish. Follow the cutroom make-video skill for the full process. Image paths returned by tools can be viewed with Read."""

mcp = MCPServer("cutroom", instructions=INSTRUCTIONS)
_music_jobs: dict[str, threading.Thread] = {}


async def bg(fn, pid: str | None = None):
    return await anyio.to_thread.run_sync(lambda: _guard(fn, pid=pid), abandon_on_cancel=True)


def _guard(fn, pid: str | None = None):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log("tool error", fn.__name__, traceback.format_exc()[-1500:])
        if isinstance(pid, str) and len(pid) > 20:
            db.emit(pid, "error", f"{fn.__name__}: {str(e)[:300]}", {"tool": fn.__name__})
        raise


def _tool_event(pid: str, tool: str, inp: dict):
    db.emit(pid, "tool", tool, {"tool": tool, "input": {k: (v if len(str(v)) < 300 else str(v)[:300] + "…") for k, v in inp.items()}})


def _up(pid: str, path: str | Path, sub: str) -> str | None:
    p = Path(path)
    return db.upload(p, f"projects/{pid}/{sub}/{p.name}")


def _plan_shot(pid: str, sid: str) -> dict:
    st = project.load(pid)
    for s in (st.get("plan") or {}).get("shots", []):
        if s.get("id") == sid:
            return s
    return {}


# ---------------------------------------------------------------- brief and plan
@mcp.tool()
async def project_start(brief: str, aspect_ratio: str = "16:9", length_s: int = 60, style: str = "") -> dict:
    """Open a project. brief = what you want; aspect_ratio 16:9 | 9:16 | 1:1; length_s target length; style = look,
    tone and references. Returns project_id, working dir and frame size."""
    def run():
        st = project.start(brief, aspect_ratio, length_s, style)
        db.emit(st["id"], "stage", "brief received", {"stage": "brief", "progress": 2})
        db.emit(st["id"], "thought", f"Brief: {brief[:400]} · {aspect_ratio} · {length_s}s · {style[:200]}")
        return {"project_id": st["id"], "dir": str(project.pdir(st["id"])), "width": st["width"], "height": st["height"],
                "aspect_ratio": aspect_ratio, "length_s": length_s}
    return await bg(run)


@mcp.tool()
async def save_plan(project_id: str, plan: dict) -> dict:
    """Save the script and shot plan: {title, logline, references:[{name,prompt}], shots:[{id, kind
    (generated|footage|graphic), duration_s, narration, direction, visual, motion?, engine?, youtube_query?, refs?,
    transition?, label?}]}. Returns the plan with Jev's engine routing for shots that don't specify one."""
    def run():
        st = project.load(project_id)
        shots = plan.get("shots") or []
        if not shots:
            raise ValueError("plan.shots is empty")
        seen = set()
        for i, s in enumerate(shots):
            s.setdefault("id", f"s{i + 1:02d}")
            if s["id"] in seen:
                raise ValueError(f"duplicate shot id {s['id']}")
            seen.add(s["id"])
        routing = {}
        todo = [s for s in shots if not s.get("engine") and "motion" not in s and s.get("kind") != "footage"]
        if todo:
            with cf.ThreadPoolExecutor(6) as ex:
                for s, r in zip(todo, ex.map(jev.route_shot, todo)):
                    if r:
                        s["jev"] = r
                        routing[s["id"]] = r
        st["plan"] = plan
        project.save(project_id, st)
        total = sum(float(s.get("duration_s") or 0) for s in shots)
        db.update(project_id, script=plan, title=plan.get("title"), logline=plan.get("logline"))
        db.stage(project_id, "plan", 8, f"plan saved: {len(shots)} shots, {total:.0f}s")
        db.emit(project_id, "thought", f"{plan.get('title', '')}: {plan.get('logline', '')}")
        return {"shots": len(shots), "planned_seconds": total, "jev_routing": routing}
    return await bg(run, project_id)


# ---------------------------------------------------------------- references, keyframes, animatic, shots
@mcp.tool()
async def gen_reference(project_id: str, name: str, prompt: str) -> dict:
    """Generate a reference image (character, location, object, style frame) used as a consistency anchor for
    keyframes and shots. Read the returned path to check it."""
    def run():
        _tool_event(project_id, "gen_reference", {"name": name, "prompt": prompt})
        out = project.pdir(project_id) / "refs" / f"{name}.png"
        r = openrouter.gen_image(prompt, out, "1:1")
        url = _up(project_id, out, "refs")
        project.put_asset(project_id, "refs", name, {"path": r["path"], "url": url, "prompt": prompt, "model": r["model"]})
        db.stage(project_id, "references", 15)
        db.emit(project_id, "reference", f"reference: {name}", {"name": name, "url": url, "model": r["model"]})
        return r | {"url": url}
    return await bg(run, project_id)


@mcp.tool()
async def gen_keyframe(project_id: str, shot_id: str, prompt: str, refs: list[str] | None = None) -> dict:
    """Generate the first frame of a shot, conditioned on named reference images. Read the returned path to check it."""
    def run():
        _tool_event(project_id, "gen_keyframe", {"shot_id": shot_id, "prompt": prompt, "refs": refs})
        st = project.load(project_id)
        ref_paths = [st["assets"]["refs"][n]["path"] for n in (refs or []) if n in st.get("assets", {}).get("refs", {})]
        out = project.pdir(project_id) / "keyframes" / f"{shot_id}.png"
        r = openrouter.gen_image(prompt, out, st.get("aspect_ratio", "16:9"), ref_paths)
        url = _up(project_id, out, "keyframes")
        project.put_asset(project_id, "keyframes", shot_id, {"path": r["path"], "url": url, "prompt": prompt, "model": r["model"]})
        db.emit(project_id, "keyframe", f"keyframe {shot_id}", {"shot_id": shot_id, "url": url, "model": r["model"]})
        return r | {"url": url}
    return await bg(run, project_id)


@mcp.tool()
async def render_animatic(project_id: str) -> dict:
    """Cut the keyframes to the plan timing with the voice (or a scratch voice) and shot/timecode burn-in. Review it
    (critique works on it too) before spending on video generation."""
    def run():
        _tool_event(project_id, "render_animatic", {})
        r = asm.assemble(project_id, "animatic")
        url = _up(project_id, r["mp4_path"], "cuts")
        db.stage(project_id, "animatic", 25)
        db.emit(project_id, "animatic", f"animatic {r['duration']:.1f}s", {"url": url, "duration": r["duration"]})
        return r | {"url": url}
    return await bg(run, project_id)


@mcp.tool()
async def gen_shot(project_id: str, shot_id: str, prompt: str, keyframe: str | None = None, motion: bool | None = None,
                   duration_s: float = 6) -> dict:
    """Generate a video shot from its keyframe. motion=true → Seedance 2.5 (strong motion), false → Veo 3.1;
    omitted → Jev decides. Falls back to a camera move over the keyframe if generation fails. Takes 1-5 minutes."""
    def run():
        st = project.load(project_id)
        a = st.get("assets", {})
        kf = keyframe or a.get("keyframes", {}).get(shot_id, {}).get("path")
        shot = _plan_shot(project_id, shot_id)
        mo = motion
        routed = None
        if mo is None:
            mo = shot.get("motion")
        if mo is None:
            routed = jev.route_shot(shot or {"visual": prompt})
            mo = bool(routed and routed["engine"] == "generated_motion")
        refs = [a["refs"][n]["path"] for n in shot.get("refs", []) if n in a.get("refs", {})]
        _tool_event(project_id, "gen_shot", {"shot_id": shot_id, "prompt": prompt, "motion": mo, "duration_s": duration_s})
        out = project.pdir(project_id) / "shots" / f"{shot_id}.mp4"
        r = openrouter.gen_video(prompt, out, duration_s, st.get("aspect_ratio", "16:9"), kf, refs, mo, pid=project_id)
        url = _up(project_id, out, "shots")
        project.put_asset(project_id, "shots", shot_id, {"path": r["path"], "url": url, "model": r["model"], "prompt": prompt})
        db.stage(project_id, "shots", 45)
        db.emit(project_id, "shot", f"shot {shot_id} · {r['model']}", {"shot_id": shot_id, "url": url, "model": r["model"],
                                                                       "fallback": r["fallback"]})
        return r | {"url": url, "jev_routing": routed}
    return await bg(run, project_id)


# ---------------------------------------------------------------- real footage
@mcp.tool()
async def search_footage(project_id: str, query: str, n: int = 6, shot_id: str | None = None) -> dict:
    """Search YouTube for Creative Commons videos. Returns title, channel, duration, license, description, chapters
    and a Jev relevance score per candidate. Pick a section and call add_clip."""
    def run():
        _tool_event(project_id, "search_footage", {"query": query, "shot_id": shot_id})
        shot = _plan_shot(project_id, shot_id) if shot_id else {}
        res = footage.search(query, n, shot_text=(shot.get("visual") or "") + " " + (shot.get("narration") or "") or query,
                             pid=project_id)
        db.stage(project_id, "footage", 50)
        for c in res[:3]:
            db.emit(project_id, "clip", f"candidate: {c['title']}", {"youtube_id": c["id"], "title": c["title"], "channel": c["channel"],
                                                                      "license": c["license"], "thumb": c["thumb"], "used": False})
        return {"candidates": res}
    return await bg(run, project_id)


@mcp.tool()
async def add_clip(project_id: str, youtube_id: str, start: float, end: float, shot_id: str) -> dict:
    """Download only [start, end] seconds of a Creative Commons video for a shot and record it in the license ledger."""
    def run():
        _tool_event(project_id, "add_clip", {"youtube_id": youtube_id, "start": start, "end": end, "shot_id": shot_id})
        meta = footage.info(youtube_id)
        if "creative commons" not in meta["license"].lower():
            raise ValueError(f"{youtube_id} is not Creative Commons licensed ({meta['license'] or 'standard YouTube license'})")
        out = project.pdir(project_id) / "clips" / f"{shot_id}.mp4"
        footage.download_section(youtube_id, start, end, out)
        url = _up(project_id, out, "clips")
        project.put_asset(project_id, "clips", shot_id, {k: v for k, v in meta.items() if k != "duration"} | {"source_duration": meta.get("duration"), "path": str(out), "start": start, "end": end, "url_media": url})
        if not db.mark_clip_used(project_id, youtube_id, start, end):
            pass
        st = db.client()
        if st is not None:
            db.insert_clip({"project_id": project_id, "youtube_id": youtube_id, "title": meta["title"], "channel": meta["channel"],
                            "license": meta["license"], "url": meta["url"], "start_s": start, "end_s": end, "used": True})
        db.emit(project_id, "clip", f"clip {shot_id}: {meta['title']}", {"youtube_id": youtube_id, "title": meta["title"],
                                                                         "channel": meta["channel"], "license": meta["license"],
                                                                         "thumb": meta["thumb"], "start": start, "end": end,
                                                                         "url": url, "used": True, "shot_id": shot_id})
        return {"path": str(out), "duration": duration(out), "url": url, "license": meta["license"], "title": meta["title"]}
    return await bg(run, project_id)


# ---------------------------------------------------------------- motion graphics
OVERLAY_TEMPLATES = {"lower_third", "data_callout", "kinetic_quote", "callout", "label"}


@mcp.tool()
async def motion_graphic(project_id: str, shot_id: str, engine: str, source: str | None = None, template: str | None = None,
                         params: dict | None = None, overlay: bool | None = None, duration_s: float | None = None) -> dict:
    """Render a motion graphic. engine: hyperframes | manim | motion_canvas | blender. Use a template with params, or
    custom source (HTML for hyperframes, a Scene class for manim, a TSX scene for motion_canvas). overlay=true renders
    with transparency on top of the shot (lower thirds default to overlay); otherwise it is the shot's picture."""
    def run():
        st = project.load(project_id)
        w, h = st.get("width", 1920), st.get("height", 1080)
        is_overlay = overlay if overlay is not None else (template in OVERLAY_TEMPLATES)
        dur = duration_s or float(_plan_shot(project_id, shot_id).get("duration_s") or 5)
        _tool_event(project_id, "motion_graphic", {"shot_id": shot_id, "engine": engine, "template": template, "params": params,
                                                   "overlay": is_overlay, "custom": bool(source)})
        out = str(project.pdir(project_id) / "gfx" / f"{shot_id}{'_overlay' if is_overlay else ''}_{engine}.{'mov' if is_overlay else 'mp4'}")
        r = _render_motion(engine, out, w, h, dur, source, template, params or {})
        path = r["path"] if isinstance(r, dict) else str(r)
        preview = r.get("preview") if isinstance(r, dict) else None
        url = _up(project_id, preview or path, "gfx")
        project.put_asset(project_id, "overlays" if is_overlay else "graphics", shot_id,
                          {"path": path, "engine": engine, "template": template, "url": url, "overlay": is_overlay})
        db.stage(project_id, "graphics", 60)
        db.emit(project_id, "graphic", f"{engine} {template or 'custom'} for {shot_id}",
                {"shot_id": shot_id, "engine": engine, "template": template, "url": url, "overlay": is_overlay})
        return {"path": path, "preview": preview, "url": url, "overlay": is_overlay, "duration": duration(path)}
    return await bg(run, project_id)


def _call(fn, **kw):
    """Call a renderer with only the keyword arguments it accepts."""
    sig = inspect.signature(fn).parameters
    if any(p.kind == p.VAR_KEYWORD for p in sig.values()):
        return fn(**kw)
    return fn(**{k: v for k, v in kw.items() if k in sig})


def _render_motion(engine, out, w, h, dur, source, template, params):
    common = {"out": out, "w": w, "h": h, "fps": 30, "duration": dur}
    if engine == "hyperframes":
        from .motion import hyperframes
        return _call(hyperframes.render, source=source, template=template, params=params, **common)
    if engine == "manim":
        from .motion import manim_r
        if template:
            return _call(manim_r.render_template, template=template, params=params, **common)
        import re
        names = re.findall(r"class\s+(\w+)\s*\(", source or "")
        return _call(manim_r.render, scene_code=source, scene_name=params.get("scene_name") or (names[-1] if names else "Main"), **common)
    if engine == "motion_canvas":
        from .motion import motion_canvas
        return _call(motion_canvas.render, scene_tsx=source, source=source, template=template, params=params, **common)
    if engine == "blender":
        from .motion import blender
        return _call(blender.render, template=template, params=params, source=source, **common)
    raise ValueError(f"unknown engine {engine!r}: use hyperframes | manim | motion_canvas | blender")


# ---------------------------------------------------------------- sound
@mcp.tool()
async def voiceover(project_id: str, segments: list[dict], voice: str | None = None) -> dict:
    """Record narration with Gemini 3.8 TTS. segments: [{shot_id, text, direction}] — text is the verbatim line (inline
    tags like <short pause> or <sigh> allowed), direction is how to say it (emotion, pace, emphasis). Returns each
    line's duration so you can fix timing."""
    def one(seg):
        sid = seg["shot_id"]
        out = project.pdir(project_id) / "audio" / f"vo_{sid}.wav"
        r = gemini_tts.tts(seg["text"], out, seg.get("direction", ""), voice)
        url = _up(project_id, out, "audio")
        project.put_asset(project_id, "voice", sid, {"path": r["path"], "duration": r["duration"], "url": url, "engine": r["engine"],
                                                     "text": seg["text"], "direction": seg.get("direction", "")})
        db.emit(project_id, "voice", f"voice {sid} · {r['duration']:.1f}s", {"shot_id": sid, "url": url, "duration": r["duration"],
                                                                            "engine": r["engine"]})
        planned = float(_plan_shot(project_id, sid).get("duration_s") or 0)
        return {"shot_id": sid, "path": r["path"], "duration": round(r["duration"], 2), "planned_s": planned,
                "overruns_by": round(max(0.0, r["duration"] + 0.6 - planned), 2) if planned else None, "engine": r["engine"]}

    def run():
        _tool_event(project_id, "voiceover", {"segments": len(segments)})
        db.stage(project_id, "voice", 68)
        with cf.ThreadPoolExecutor(4) as ex:
            res = list(ex.map(one, segments))
        return {"lines": res, "total_s": round(sum(x["duration"] for x in res), 2)}
    return await bg(run, project_id)


@mcp.tool()
async def music(project_id: str, prompt: str, length_s: float | None = None, wait: bool = False) -> dict:
    """Score the film with ElevenLabs music (instrumental). Runs in the background by default; assemble waits for it.
    prompt: genre, instrumentation, mood arc and tempo, e.g. 'restrained documentary score, felt piano and low strings,
    builds gently, 80 bpm'."""
    def compose():
        st = project.load(project_id)
        total = length_s or (sum(float(s.get("duration_s") or 0) for s in (st.get("plan") or {}).get("shots", [])) + 4) or 60
        out = project.pdir(project_id) / "audio" / "music.wav"
        r = elevenlabs.music(prompt, total, out)
        url = _up(project_id, out, "audio")
        project.put_asset(project_id, "music", "main", {"path": r["path"], "duration": r["duration"], "url": url, "engine": r["engine"],
                                                        "prompt": prompt})
        db.emit(project_id, "music", f"score · {r['engine']} · {r['duration']:.0f}s", {"url": url, "engine": r["engine"],
                                                                                     "title": prompt[:80]})
        return r | {"url": url}

    def run():
        _tool_event(project_id, "music", {"prompt": prompt, "length_s": length_s})
        db.stage(project_id, "music", 72)
        if wait:
            return compose()
        t = threading.Thread(target=lambda: _guard(compose, pid=project_id), daemon=True)
        t.start()
        _music_jobs[project_id] = t
        return {"status": "composing in the background; assemble will wait for it"}
    return await bg(run, project_id)


# ---------------------------------------------------------------- edit, captions, critique
@mcp.tool()
async def assemble(project_id: str, mode: str = "final") -> dict:
    """Build the OpenTimelineIO timeline from the plan and assets and render it. mode: animatic | final.
    Returns the .otio path, the mp4 path, the duration and the shot layout (start/end per shot)."""
    def run():
        t = _music_jobs.get(project_id)
        if t and t.is_alive() and mode == "final":
            db.emit(project_id, "thought", "waiting for the score to finish")
            t.join(timeout=240)
        _tool_event(project_id, "assemble", {"mode": mode})
        st = project.load(project_id)
        recut = mode == "final" and st.get("round", 0) >= 1
        db.stage(project_id, "recut" if recut else ("assemble" if mode == "final" else "animatic"), 94 if recut else (80 if mode == "final" else 25))
        r = asm.assemble(project_id, mode)
        url = _up(project_id, r["mp4_path"], "cuts")
        _up(project_id, r["otio_path"], "cuts")
        if mode == "animatic":
            db.emit(project_id, "animatic", f"animatic {r['duration']:.1f}s", {"url": url, "duration": r["duration"]})
        else:
            db.emit(project_id, "cut", f"cut round {r['round']} · {r['duration']:.1f}s", {"round": r["round"], "url": url,
                                                                                        "duration": r["duration"]})
        return r | {"url": url}
    return await bg(run, project_id)


def _overlay_windows(st: dict, cut_path: str) -> list[tuple[float, float]]:
    """Times when an overlay graphic is on screen in this cut, read from its .otio V2 track."""
    import opentimelineio as otio
    for c in st.get("assets", {}).get("cuts", {}).values():
        if Path(c.get("path", "")).stem == Path(cut_path).stem.replace("_captioned", "") and c.get("otio"):
            try:
                tl = otio.adapters.read_from_file(c["otio"])
                return [(it.range_in_parent().start_time.to_seconds(), it.range_in_parent().end_time_exclusive().to_seconds())
                        for tk in tl.tracks if tk.name.startswith("V2") for it in tk if isinstance(it, otio.schema.Clip)]
            except Exception:  # noqa: BLE001
                return []
    return []


@mcp.tool()
async def captions(project_id: str, cut_path: str, corrections: dict | None = None) -> dict:
    """Transcribe the cut with word-level timing and burn in captions that highlight each word as it is spoken.
    corrections: {heard_word: correct_word} for names the recogniser gets wrong."""
    def run():
        _tool_event(project_id, "captions", {"cut_path": Path(cut_path).name, "corrections": corrections})
        st = project.load(project_id)
        db.stage(project_id, "captions", 85)
        r = cap.captions(cut_path, st.get("width", 1920), st.get("height", 1080), corrections, _overlay_windows(st, cut_path))
        url = _up(project_id, r["burned_mp4"], "cuts")
        _up(project_id, r["srt"], "cuts")
        db.emit(project_id, "captions", f"captions · {r['words']} words · {r['asr']}", {"url": url, "words": r["words"]})
        return r | {"url": url}
    return await bg(run, project_id)


@mcp.tool()
async def critique(project_id: str, cut_path: str) -> dict:
    """Review any mp4 (a cut, the animatic, a generated shot or a clip): contact sheets labelled with timecode and
    shot id (Read them), transcript vs script diff, loudness, black/frozen/silent spans, music ducking, and Jev's
    check of the narration style. Returns a list of issues to fix."""
    def run():
        _tool_event(project_id, "critique", {"cut_path": Path(cut_path).name})
        db.stage(project_id, "critique", 90)
        r = critic.critique(project_id, cut_path)
        urls = [_up(project_id, p, "frames") for p in r["contact_sheets"]]
        db.emit(project_id, "critique", f"critique round {r['round']}: {len(r['issues'])} issues",
                {"round": r["round"], "issues": r["issues"][:20], "contact_sheet_url": urls[0] if urls else None,
                 "contact_sheets": urls, "script_match": r["script_match"], "metrics": {k: v for k, v in r["metrics"].items()}})
        st = project.load(project_id)
        st.setdefault("critiques", []).append({"round": r["round"], "issues": r["issues"], "cut": cut_path})
        project.save(project_id, st)
        db.update(project_id, critique=st["critiques"])
        return r | {"contact_sheet_urls": urls}
    return await bg(run, project_id)


@mcp.tool()
async def upscale_4k(project_id: str, cut_path: str, scale: int = 2) -> dict:
    """Upscale the finished cut to 4K with Real-ESRGAN (slow: minutes). Run after the final critique, before publish."""
    def run():
        from .upscale import upscale_4k as up
        _tool_event(project_id, "upscale_4k", {"cut_path": Path(cut_path).name, "scale": scale})
        db.stage(project_id, "upscale", 97)
        out = str(Path(cut_path).with_name(Path(cut_path).stem + "_4k.mp4"))
        last = {"t": 0}

        def prog(p):
            if time.time() - last["t"] > 10:
                last["t"] = time.time()
                db.emit(project_id, "thought", f"upscaling to 4K… {int(p * 100) if p <= 1 else int(p)}%")
        path = up(cut_path, out, scale=scale, on_progress=prog)
        path = path if isinstance(path, str) else (path.get("path") if isinstance(path, dict) else out)
        url = _up(project_id, path, "cuts")
        project.put_asset(project_id, "cuts", "4k", {"path": path, "url": url})
        db.emit(project_id, "upscale", "4K ready", {"url": url})
        if url:
            db.update(project_id, video_4k_url=url)
        return {"path": path, "url": url}
    return await bg(run, project_id)


@mcp.tool()
async def publish(project_id: str, cut_path: str, title: str, logline: str = "") -> dict:
    """Publish the final film: upload it (and the 4K version if made), set the poster, write the credits/license
    ledger and mark the project done."""
    def run():
        _tool_event(project_id, "publish", {"cut_path": Path(cut_path).name, "title": title})
        st = project.load(project_id)
        cut = Path(cut_path)
        web = cut
        if cut.stat().st_size > 45 * 1024 * 1024:  # keep under the storage upload limit
            web = cut.with_name(cut.stem + "_web.mp4")
            ffmpeg("-i", cut, "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-maxrate", "5M", "-bufsize", "10M",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", web)
        url = _up(project_id, web, "final")
        poster = cut.with_name(cut.stem + "_poster.jpg")
        ffmpeg("-ss", f"{min(3.0, duration(cut) / 3):.2f}", "-i", cut, "-frames:v", "1", "-q:v", "2", poster)
        poster_url = _up(project_id, poster, "final")
        a = st.get("assets", {})
        credits = []
        for sid, c in a.get("clips", {}).items():
            credits.append({"kind": "footage", "title": c.get("title"), "channel": c.get("channel"), "url": c.get("url"),
                            "license": c.get("license"), "used": [[c.get("start"), c.get("end")]], "shot_id": sid})
        m = a.get("music", {}).get("main")
        if m:
            credits.append({"kind": "music", "title": m.get("prompt", "")[:80], "channel": m.get("engine"), "url": None,
                            "license": "generated for this film" if m.get("engine") != "synth-pad" else "synthesised"})
        models = sorted({x.get("model") for k in ("shots", "keyframes", "refs") for x in a.get(k, {}).values() if x.get("model")})
        if models:
            credits.append({"kind": "generated", "title": "Generated imagery and video", "channel": ", ".join(models),
                            "url": None, "license": "generated"})
        k4 = a.get("cuts", {}).get("4k", {}).get("url")
        db.update(project_id, status="done", stage="done", progress=100, title=title, logline=logline, video_url=url,
                  poster_url=poster_url, credits=credits, **({"video_4k_url": k4} if k4 else {}))
        db.emit(project_id, "done", f"published: {title}", {"video_url": url, "video_4k_url": k4, "poster_url": poster_url})
        st["published"] = {"url": url, "poster": poster_url, "title": title}
        project.save(project_id, st)
        return {"url": url, "poster_url": poster_url, "video_4k_url": k4, "credits": credits,
                "studio": f"{(config.get('CUTROOM_SITE_URL') or '').rstrip('/')}/p/{project_id}" if config.get("CUTROOM_SITE_URL") else None}
    return await bg(run, project_id)


@mcp.tool()
async def get_project(project_id: str) -> dict:
    """The project's plan, assets produced so far (paths and urls), cuts and critique history."""
    def run():
        st = project.load(project_id)
        return {k: st.get(k) for k in ("id", "brief", "aspect_ratio", "length_s", "style", "width", "height", "plan", "assets",
                                       "round", "layout", "critiques", "published")}
    return await bg(run, project_id)


# ---------------------------------------------------------------- stdio with a clean protocol channel
def main():
    """Keep stdout exclusively for MCP: anything else (yt-dlp, ffmpeg, prints) is routed to stderr at the fd level."""
    proto_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    async def serve():
        from mcp.server.stdio import stdio_server
        out = anyio.wrap_file(io.TextIOWrapper(os.fdopen(proto_fd, "wb", buffering=0), encoding="utf-8", write_through=True))
        async with stdio_server(stdout=out) as (r, w):
            await mcp._lowlevel_server.run(r, w, mcp._lowlevel_server.create_initialization_options())

    log("cutroom MCP server starting; projects in", config.PROJECTS)
    anyio.run(serve)


if __name__ == "__main__":
    main()

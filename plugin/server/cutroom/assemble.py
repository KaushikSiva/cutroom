"""Assembly: the plan + assets become an OpenTimelineIO timeline (.otio), and the .otio is rendered with ffmpeg.

Tracks: V1 picture (one item per shot), V2 overlay graphics with alpha (lower thirds etc.), A1 voice, A2 music.
Animatic mode uses keyframe stills (or cards) with a slow push-in, a scratch voice and a shot/timecode burn-in.
"""
import shutil
from pathlib import Path

import opentimelineio as otio

from . import project
from .config import log
from .providers import gemini_tts, openrouter
from .util import FONT, duration, esc_drawtext, ffmpeg, has_audio

FPS = 30
VO_LEAD = 0.2          # voice starts this long after the cut
XFADE = 0.5            # dissolve length
STILL = {".png", ".jpg", ".jpeg", ".webp"}
BG = "0x0b0d14"
SLUG_FONT = Path(__file__).parent / "motion" / "fonts" / "fraunces-semibold.ttf"


def rt(seconds: float) -> otio.opentime.RationalTime:
    return otio.opentime.RationalTime(round(seconds * FPS), FPS)


def tr(start: float, dur: float) -> otio.opentime.TimeRange:
    return otio.opentime.TimeRange(rt(start), rt(dur))


def _visual(shot: dict, assets: dict, mode: str) -> tuple[str | None, str, float]:
    """-> (path, source_kind, source_in). Picks the best picture available for the shot."""
    sid = shot["id"]
    gfx = assets.get("graphics", {}).get(sid)
    clip = assets.get("clips", {}).get(sid)
    gen = assets.get("shots", {}).get(sid)
    kf = assets.get("keyframes", {}).get(sid)
    if mode == "animatic":
        order = [("keyframe", kf), ("graphic", gfx), ("clip", clip)]
    else:
        pref = {"graphic": ["graphic", "clip", "shot", "keyframe"], "footage": ["clip", "shot", "graphic", "keyframe"]}.get(
            shot.get("kind"), ["shot", "clip", "graphic", "keyframe"])
        table = {"graphic": gfx, "clip": clip, "shot": gen, "keyframe": kf}
        order = [(k, table[k]) for k in pref]
    for kind, a in order:
        if a and a.get("path") and Path(a["path"]).exists():
            # downloaded clips are already trimmed to [start, end]
            return a["path"], kind, 0.0
    return None, "card", 0.0


def build_timeline(pid: str, mode: str = "final") -> tuple[otio.schema.Timeline, Path, list[dict]]:
    st = project.load(pid)
    plan = st.get("plan") or {}
    shots = plan.get("shots") or []
    if not shots:
        raise ValueError("no plan saved: call save_plan first")
    assets = st.get("assets", {})
    d = project.pdir(pid)
    tl = otio.schema.Timeline(name=plan.get("title") or st.get("brief", "Cutroom")[:60])
    tl.global_start_time = rt(0)
    v1 = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    v2 = otio.schema.Track(name="V2 overlays", kind=otio.schema.TrackKind.Video)
    a1 = otio.schema.Track(name="A1 voice", kind=otio.schema.TrackKind.Audio)
    a2 = otio.schema.Track(name="A2 music", kind=otio.schema.TrackKind.Audio)
    a3 = otio.schema.Track(name="A3 source audio", kind=otio.schema.TrackKind.Audio)
    a3_cursor = 0.0
    t = 0.0
    layout = []
    v2_cursor = a1_cursor = 0.0
    for shot in shots:
        sid = shot["id"]
        voice = assets.get("voice", {}).get(sid)
        if mode == "animatic" and not voice and shot.get("narration"):
            scratch = d / "audio" / f"scratch_{sid}.wav"
            if not scratch.exists():
                gemini_tts.say(shot["narration"], scratch)
            voice = {"path": str(scratch), "duration": duration(scratch)}
        vdur = float(voice["duration"]) if voice else 0.0
        dur = max(float(shot.get("duration_s") or 4), VO_LEAD + vdur + 0.4 if vdur else 0)
        path, kind, src_in = _visual(shot, assets, mode)
        if not path:
            card = d / "keyframes" / f"card_{sid}.png"
            openrouter.placeholder_card(shot.get("visual") or shot.get("narration") or sid, card, st.get("aspect_ratio", "16:9"))
            path, kind = str(card), "card"
        clip = otio.schema.Clip(name=sid, media_reference=otio.schema.ExternalReference(target_url=str(path)),
                                source_range=tr(src_in, dur))
        clip.metadata["cutroom"] = {"shot_id": sid, "source": kind, "still": Path(path).suffix.lower() in STILL,
                                    "graphic": kind == "graphic", "label": shot.get("label") or "",
                                    "slug": shot.get("slug") or "",
                                    "transition": "dissolve" if shot.get("transition") == "dissolve" and t > 0 else "cut"}
        v1.append(clip)
        # overlay graphic for this shot (alpha), slightly after the cut
        ov = assets.get("overlays", {}).get(sid)
        if ov and Path(ov["path"]).exists() and mode == "final":
            ostart, odur = t + 0.4, min(dur - 0.5, duration(ov["path"]) or dur)
            if ostart > v2_cursor:
                v2.append(otio.schema.Gap(source_range=tr(0, ostart - v2_cursor)))
            oc = otio.schema.Clip(name=f"{sid}-overlay", media_reference=otio.schema.ExternalReference(target_url=ov["path"]),
                                  source_range=tr(0, odur))
            v2.append(oc)
            v2_cursor = ostart + odur
        # original sound of a real clip (a speech, a famous line): plays under no narration, music ducks under it
        if shot.get("keep_audio") and kind not in ("card", "graphic") and Path(path).suffix.lower() not in STILL:
            if t > a3_cursor:
                a3.append(otio.schema.Gap(source_range=tr(0, t - a3_cursor)))
            src_clip = otio.schema.Clip(name=f"{sid}-src", media_reference=otio.schema.ExternalReference(target_url=str(path)),
                                        source_range=tr(src_in, dur))
            src_clip.metadata["cutroom"] = {"gain": float(shot.get("source_gain", 1.0))}
            a3.append(src_clip)
            a3_cursor = t + dur
        if voice:
            vstart = t + VO_LEAD
            if vstart > a1_cursor:
                a1.append(otio.schema.Gap(source_range=tr(0, vstart - a1_cursor)))
            a1.append(otio.schema.Clip(name=f"{sid}-vo", media_reference=otio.schema.ExternalReference(target_url=voice["path"]),
                                       source_range=tr(0, vdur)))
            a1_cursor = vstart + vdur
        layout.append({"shot_id": sid, "start": round(t, 2), "end": round(t + dur, 2), "source": kind,
                       "narration": shot.get("narration", "")})
        t += dur
    music = assets.get("music", {}).get("main")
    if music and Path(music["path"]).exists():
        a2.append(otio.schema.Clip(name="score", media_reference=otio.schema.ExternalReference(target_url=music["path"]),
                                   source_range=tr(0, t)))
    tl.tracks.extend([v1, v2, a1, a2, a3])
    out = d / "cuts" / f"{mode}.otio"
    otio.adapters.write_to_file(tl, str(out))
    return tl, out, layout


def render_otio(otio_path: Path, out_mp4: Path, w: int, h: int, mode: str = "final") -> float:
    """Renders an .otio produced by build_timeline. Returns duration in seconds."""
    tl = otio.adapters.read_from_file(str(otio_path))
    work = out_mp4.parent / f"_{out_mp4.stem}_segs"
    work.mkdir(exist_ok=True)
    tracks = {tk.name: tk for tk in tl.tracks}
    v1 = tracks["V1"]
    items = [it for it in v1 if isinstance(it, otio.schema.Clip)]
    segs = []
    fit = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={FPS}"
    for i, item in enumerate(items):
        meta = item.metadata.get("cutroom", {})
        src = item.media_reference.target_url
        sr = item.source_range
        dur, sin = sr.duration.to_seconds(), sr.start_time.to_seconds()
        nxt = items[i + 1].metadata.get("cutroom", {}) if i + 1 < len(items) else {}
        render_dur = dur + (XFADE if nxt.get("transition") == "dissolve" else 0.0)   # tail that the dissolve eats
        seg = work / f"{i:03d}.mp4"
        burn = ""
        if mode == "animatic":
            start = item.range_in_parent().start_time.to_seconds()
            label = esc_drawtext(f"{meta.get('shot_id', '')}  {int(start // 60):02d}:{start % 60:05.2f}  {meta.get('source', '')}")
            burn = (f",drawtext=fontfile={FONT}:text='{label}':x=24:y=h-th-24:fontsize={int(h * 0.028)}:"
                    f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10")
        if mode == "final" and meta.get("slug"):
            slug = esc_drawtext(meta["slug"].upper())
            fade = f"if(lt(t,0.6),t/0.6,if(gt(t,{dur - 0.6:.3f}),max(0,({dur:.3f}-t)/0.6),1))"
            burn += (f",drawtext=fontfile={SLUG_FONT}:text='{slug}':x=w*0.045:y=h*0.93-th:fontsize={int(h * 0.019)}:"
                     f"fontcolor=white:alpha='0.82*{fade}':shadowcolor=black@0.6:shadowx=1:shadowy=1")
        enc = ["-t", f"{render_dur:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), seg]
        if meta.get("still"):
            tmp = work / f"{i:03d}_kb.mp4"
            openrouter.ken_burns(src, tmp, render_dur, _aspect(w, h))
            ffmpeg("-i", tmp, "-vf", f"{fit},format=yuv420p{burn}", *enc)
        elif meta.get("graphic"):
            ffmpeg("-f", "lavfi", "-i", f"color=c={BG}:s={w}x{h}:r={FPS}:d={render_dur:.3f}", "-ss", f"{sin:.3f}", "-i", src,
                   "-filter_complex", f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,fps={FPS},"
                                      f"tpad=stop_mode=clone:stop_duration={render_dur:.3f}[g];[0:v][g]overlay=(W-w)/2:(H-h)/2:shortest=0,"
                                      f"setsar=1,format=yuv420p{burn}", *enc)
        else:
            avail = max(0.1, duration(src) - sin)
            slow = ""
            if avail < render_dur:   # short source: slow it a little (up to 1.6x) instead of freezing
                factor = min(1.6, render_dur / avail)
                slow = f",setpts={factor:.4f}*PTS"
            ffmpeg("-ss", f"{sin:.3f}", "-i", src,
                   "-vf", f"{fit}{slow},tpad=stop_mode=clone:stop_duration={render_dur:.3f},format=yuv420p{burn}", *enc)
        segs.append((seg, render_dur, meta.get("transition", "cut")))
    picture = work / "picture.mp4"
    if any(tn == "dissolve" for _, _, tn in segs[1:]):
        args, fc = [], []
        for k, (seg, _, _) in enumerate(segs):
            args += ["-i", seg]
            fc.append(f"[{k}:v]fps={FPS},settb=AVTB,format=yuv420p[s{k}]")
        cur, length = "s0", segs[0][1]
        for k in range(1, len(segs)):
            _, ln, tn = segs[k]
            if tn == "dissolve":
                fc.append(f"[{cur}][s{k}]xfade=transition=fade:duration={XFADE}:offset={length - XFADE:.3f}[x{k}]")
                length += ln - XFADE
            else:
                fc.append(f"[{cur}][s{k}]concat=n=2:v=1:a=0,settb=AVTB[x{k}]")
                length += ln
            cur = f"x{k}"
        ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "18", "-pix_fmt", "yuv420p", picture)
    else:
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{seg.resolve()}'\n" for seg, _, _ in segs))
        ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", picture)
    total = duration(picture)

    # overlays (V2)
    ov_items = [(it.media_reference.target_url, it.range_in_parent()) for it in tracks.get("V2 overlays", [])
                if isinstance(it, otio.schema.Clip)]
    if ov_items:
        args, fc, last = ["-i", picture], [], "0:v"
        for k, (src, rng) in enumerate(ov_items, start=1):
            a, b = rng.start_time.to_seconds(), rng.end_time_exclusive().to_seconds()
            args += ["-i", src]
            fc.append(f"[{k}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,setpts=PTS-STARTPTS+{a:.3f}/TB[o{k}]")
            fc.append(f"[{last}][o{k}]overlay=(W-w)/2:(H-h)/2:enable='between(t,{a:.3f},{b:.3f})':eof_action=pass[v{k}]")
            last = f"v{k}"
        fc.append(f"[{last}]format=yuv420p[vout]")
        layered = work / "layered.mp4"
        ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", "[vout]", "-t", f"{total:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", layered)
        picture = layered

    # audio: A1 voice placed by its timeline position, A2 music ducked under the voice
    voices = [(it.media_reference.target_url, it.range_in_parent().start_time.to_seconds())
              for it in tracks.get("A1 voice", []) if isinstance(it, otio.schema.Clip)]
    music = [it.media_reference.target_url for it in tracks.get("A2 music", []) if isinstance(it, otio.schema.Clip)]
    args, fc, n = ["-i", picture], [], 1
    vo_labels = []
    for src, start in voices:
        args += ["-i", src]
        ms = int(start * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[vo{n}]")
        vo_labels.append(f"[vo{n}]")
        n += 1
    for it in tracks.get("A3 source audio", []):
        if not isinstance(it, otio.schema.Clip) or not has_audio(it.media_reference.target_url):
            continue
        sr, start = it.source_range, it.range_in_parent().start_time.to_seconds()
        gain = it.metadata.get("cutroom", {}).get("gain", 1.0)
        args += ["-ss", f"{sr.start_time.to_seconds():.3f}", "-t", f"{sr.duration.to_seconds():.3f}", "-i", it.media_reference.target_url]
        ms = int(start * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain:.2f},"
                  f"afade=t=in:d=0.15,afade=t=out:st={max(0, sr.duration.to_seconds() - 0.3):.3f}:d=0.3,adelay={ms}|{ms}[vo{n}]")
        vo_labels.append(f"[vo{n}]")
        n += 1
    if vo_labels:
        fc.append(f"{''.join(vo_labels)}amix=inputs={len(vo_labels)}:normalize=0,apad,atrim=0:{total:.3f}[vo]")
    if music:
        args += ["-stream_loop", "-1", "-i", music[0]]
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},volume=0.55,"
                  f"afade=t=in:d=1.5,afade=t=out:st={max(0, total - 3):.3f}:d=3[mu]")
        n += 1
    if vo_labels and music:
        fc.append("[vo]asplit=2[vo1][vo2]")
        fc.append("[mu][vo2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450:makeup=1[duck]")
        fc.append("[vo1][duck]amix=inputs=2:normalize=0[mix]")
    elif vo_labels:
        fc.append("[vo]anull[mix]")
    elif music:
        fc.append("[mu]anull[mix]")
    else:
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append(f"[{n}:a]anull[mix]")
    fc.append("[mix]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_mp4)
    shutil.rmtree(work, ignore_errors=True)   # intermediate segments can be gigabytes on long films
    return duration(out_mp4)


def _aspect(w: int, h: int) -> str:
    return {(1920, 1080): "16:9", (1080, 1920): "9:16", (1080, 1080): "1:1", (1080, 1350): "4:5"}.get((w, h), "16:9")


def assemble(pid: str, mode: str = "final") -> dict:
    st = project.load(pid)
    w, h = st.get("width", 1920), st.get("height", 1080)
    tl, otio_path, layout = build_timeline(pid, mode)
    rnd = st.get("round", 0) + (1 if mode == "final" else 0)
    out = project.pdir(pid) / "cuts" / ("animatic.mp4" if mode == "animatic" else f"cut_r{rnd}.mp4")
    log(f"rendering {mode} -> {out}")
    dur = render_otio(otio_path, out, w, h, mode)
    st = project.load(pid)
    if mode == "final":
        st["round"] = rnd
    st.setdefault("assets", {}).setdefault("cuts", {})["animatic" if mode == "animatic" else f"r{rnd}"] = {
        "path": str(out), "otio": str(otio_path), "duration": dur, "layout": layout}
    st["layout"] = layout
    project.save(pid, st)
    return {"otio_path": str(otio_path), "mp4_path": str(out), "duration": round(dur, 2), "round": rnd, "layout": layout,
            "has_audio": has_audio(out)}

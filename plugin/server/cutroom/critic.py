"""Self-critique of a cut: contact sheets (frames at every shot + regular samples) for Claude to look at, transcript vs
script, and technical checks (black, frozen picture, silence, loudness), plus Jev's read of the narration style."""
import difflib
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import project
from .providers import asr, jev
from .util import duration, ffmpeg, run

TILE_W = 480


def _frames(cut: Path, times: list[tuple[float, str]], out_dir: Path) -> list[tuple[Path, str]]:
    out = []
    for i, (t, label) in enumerate(times):
        f = out_dir / f"f{i:03d}.jpg"
        try:
            ffmpeg("-ss", f"{t:.2f}", "-i", cut, "-frames:v", "1", "-vf", f"scale={TILE_W}:-2", "-q:v", "3", f)
            out.append((f, label))
        except RuntimeError:
            pass
    return out


def _sheets(frames: list[tuple[Path, str]], out_dir: Path, cols=4, rows=3) -> list[str]:
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    sheets = []
    per = cols * rows
    for s in range(0, len(frames), per):
        chunk = frames[s:s + per]
        ims = [Image.open(p) for p, _ in chunk]
        tw, th = ims[0].size
        sheet = Image.new("RGB", (cols * tw, ((len(ims) - 1) // cols + 1) * (th + 24)), (12, 12, 16))
        d = ImageDraw.Draw(sheet)
        for i, (im, (_, label)) in enumerate(zip(ims, chunk)):
            x, y = (i % cols) * tw, (i // cols) * (th + 24)
            sheet.paste(im, (x, y + 24))
            d.text((x + 6, y + 4), label, fill=(240, 200, 80), font=font)
        p = out_dir / f"contact_{s // per + 1}.jpg"
        sheet.save(p, quality=88)
        sheets.append(str(p))
    return sheets


def _detect(cut: Path) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", cut, "-vf", "blackdetect=d=0.4:pix_th=0.10,freezedetect=n=-60dB:d=2",
             "-af", "silencedetect=noise=-42dB:d=1.5,ebur128", "-f", "null", "-"], check=False, timeout=900)
    err = p.stderr
    black = [float(x) for x in re.findall(r"black_start:([\d.]+)", err)]
    freeze = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", err)]
    silence = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    momentary = [(float(t), float(m)) for t, m in re.findall(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)", err) if m != "-inf"]
    return {"black_at": black, "freeze_at": freeze, "silence_at": silence, "integrated_lufs": float(lufs[-1]) if lufs else None,
            "_momentary": momentary}


def _ducking(momentary: list[tuple[float, float]], words: list[dict], total: float) -> dict | None:
    """Music should sit well under the voice: compare loudness while someone speaks with loudness in the pauses."""
    if not momentary or not words:
        return None
    def speaking(t):
        return any(w["start"] - 0.2 <= t <= w["end"] + 0.2 for w in words)
    sp = [m for t, m in momentary if speaking(t)]
    gap = [m for t, m in momentary if not speaking(t) and 1.0 < t < total - 1.5]
    if len(sp) < 10 or len(gap) < 10:
        return None
    sp_l, gap_l = sorted(sp)[len(sp) // 2], sorted(gap)[len(gap) // 2]
    return {"speech_lufs_median": round(sp_l, 1), "pause_lufs_median": round(gap_l, 1), "headroom_lu": round(sp_l - gap_l, 1)}


def _norm(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", re.sub(r"<[^>]+>", " ", s.lower())).split()


def critique(pid: str, cut_path: str, every_s: float | None = None) -> dict:
    st = project.load(pid)
    cut = Path(cut_path)
    total = duration(cut)
    rnd = st.get("round", 0)
    out_dir = project.pdir(pid) / "frames" / f"r{rnd}_{cut.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)
    # shot layout only applies when this file is one of the project's own cuts (critique also works on any mp4)
    layout = next((c.get("layout") or [] for c in st.get("assets", {}).get("cuts", {}).values()
                   if Path(c.get("path", "")).resolve() == cut.resolve() or
                   Path(c.get("path", "")).stem == cut.stem.replace("_captioned", "")), [])
    times = []
    for sh in layout:
        if sh["end"] <= total + 0.1:
            times.append(((sh["start"] + sh["end"]) / 2, f"{sh['shot_id']} {sh['start']:.1f}-{sh['end']:.1f}s {sh['source']}"))
    step = every_s or max(2.0, total / 24)
    t = 0.5
    while t < total and len(times) < 48:
        if all(abs(t - x) > step / 2 for x, _ in times):
            times.append((t, f"{t:.1f}s"))
        t += step
    times.sort()
    sheets = _sheets(_frames(cut, times, out_dir), out_dir)
    metrics = _detect(cut)
    tr = asr.words(cut)
    script = " ".join(sh.get("narration", "") for sh in (st.get("plan") or {}).get("shots", [])) if layout else ""
    a, b = _norm(script), _norm(tr["text"])
    match = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    issues = []
    diff = []
    if a and b:
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if op != "equal":
                diff.append({"op": op, "script": " ".join(a[i1:i2]), "heard": " ".join(b[j1:j2])})
    for sh in layout:
        said = " ".join(w["word"] for w in tr["words"] if sh["start"] <= w["start"] < sh["end"])
        want = sh.get("narration") or ""
        if want and difflib.SequenceMatcher(None, _norm(want), _norm(said)).ratio() < 0.6:
            issues.append({"severity": "high", "shot_id": sh["shot_id"], "at": sh["start"],
                           "issue": "voice doesn't match the script in this shot (cut off, mistimed or mispronounced)",
                           "heard": said[:200], "expected": want[:200]})
    for x in metrics["black_at"]:
        if x > 0.5:
            issues.append({"severity": "high", "at": x, "issue": "black frames"})
    for x in metrics["freeze_at"]:
        issues.append({"severity": "medium", "at": x, "issue": "picture frozen for 2 s or more"})
    for x in metrics["silence_at"]:
        if 1.0 < x < total - 2:
            issues.append({"severity": "low", "at": x, "issue": "silence gap (no voice or music)"})
    duck = _ducking(metrics.pop("_momentary"), tr["words"], total)
    metrics["ducking"] = duck
    if duck and duck["headroom_lu"] < 6:
        issues.append({"severity": "medium", "issue": f"music competes with the voice: only {duck['headroom_lu']} LU between speech and pauses; duck harder or lower the score"})
    if metrics["integrated_lufs"] is not None and abs(metrics["integrated_lufs"] + 16) > 2.5:
        issues.append({"severity": "medium", "issue": f"loudness {metrics['integrated_lufs']} LUFS, target -16"})
    style = jev.judge_narration(script or tr["text"])
    if style:
        if style["punchy"] > 0.6:
            issues.append({"severity": "medium", "issue": "narration leans on short punchy fragments; rewrite as connected professorial prose"})
        if style["numbers"] > 0.6:
            issues.append({"severity": "medium", "issue": "narration is crowded with numbers; keep one figure where it matters"})
        if style["cliche"] > 0.5:
            issues.append({"severity": "medium", "issue": "narration uses chatbot/marketing clichés"})
        if style["professor"] < 1.5:
            issues.append({"severity": "low", "issue": "narration doesn't yet sound like a university professor"})
    return {"round": rnd, "contact_sheets": sheets, "transcript": tr["text"], "asr": tr["engine"], "script_match": round(match, 3), "transcript_diff": diff[:40],
            "metrics": metrics, "narration_style": style, "issues": issues, "duration": round(total, 2),
            "instructions": "Read every contact sheet image before deciding. Fix high issues, then re-run assemble(mode='final')."}

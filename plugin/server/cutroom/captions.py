"""Word-level captions: ASR on the cut → karaoke-highlighted ASS (each word lights up as it's spoken) → burned in."""
from pathlib import Path

from .providers import asr
from .util import ffmpeg

HILITE = "&H0000D7FF"   # ASS colours are &HAABBGGRR: warm gold
BASE = "&H00FFFFFF"


def _ts(t: float, ass=True) -> str:
    t = max(0.0, t)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}" if ass else f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def events(words: list[dict], max_chars: int) -> list[list[list[dict]]]:
    """Groups words into caption events of at most two lines of `max_chars`, breaking at sentence ends and pauses."""
    out, cur = [], []

    def fits(ws):
        return len(_split(ws, max_chars)) <= 2 and all(len(" ".join(x["word"] for x in ln)) <= max_chars for ln in _split(ws, max_chars))

    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > 0.7 or not fits(cur + [w])):
            out.append(_split(cur, max_chars)); cur = []
        cur.append(w)
        if w["word"][-1:] in ".?!" and len(" ".join(x["word"] for x in cur)) > max_chars * 0.6:
            out.append(_split(cur, max_chars)); cur = []
    if cur:
        out.append(_split(cur, max_chars))
    return out


def _split(ws: list[dict], max_chars: int) -> list[list[dict]]:
    """Balanced split into lines no longer than max_chars."""
    text = " ".join(x["word"] for x in ws)
    if len(text) <= max_chars or len(ws) < 2:
        return [ws]
    best, best_cost = None, 1e9
    for k in range(1, len(ws)):
        a, b = " ".join(x["word"] for x in ws[:k]), " ".join(x["word"] for x in ws[k:])
        cost = abs(len(a) - len(b)) + (1000 if len(a) > max_chars or len(b) > max_chars else 0)
        if cost < best_cost:
            best, best_cost = k, cost
    if best_cost >= 1000:
        return [ws[:best], ws[best:], []][:3]  # signals "too long" to the caller via 3 lines
    return [ws[:best], ws[best:]]


def _layout(w: int, h: int) -> tuple[int, int, int]:
    """-> (max_chars, font size, bottom margin) per aspect: wider lines in 16:9, shorter in vertical/square; inside the
    title-safe area and clear of the platform UI zone at the bottom of vertical video."""
    if w > h:
        return 32, int(h * 0.058), int(h * 0.08)
    if h > w:
        return 22, int(w * 0.07), int(h * 0.20)
    return 22, int(w * 0.062), int(h * 0.12)


def _apply(words: list[dict], corrections: dict | None) -> list[dict]:
    if not corrections:
        return words
    low = {k.lower(): v for k, v in corrections.items()}
    out = []
    for w in words:
        core = w["word"].strip(".,!?;:\"'").lower()
        if core in low:
            punct = w["word"][len(w["word"].rstrip(".,!?;:")):]
            w = {**w, "word": low[core] + punct}
        out.append(w)
    return out


def write_ass(words: list[dict], path: Path, w: int, h: int, avoid: list[tuple[float, float]] | None = None) -> list[tuple[float, float, str]]:
    max_chars, size, margin_v = _layout(w, h)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,Helvetica Neue,{size},{HILITE},{BASE},&H00101010,&H64000000,1,0,0,0,100,100,0.5,0,1,{max(2, size // 16)},"
            f"{max(1, size // 30)},2,{int(w * 0.1)},{int(w * 0.1)},{margin_v},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    evs = events(words, max_chars)
    rows, timed = [], []
    for i, lines_ in enumerate(evs):
        flat = [x for ln in lines_ for x in ln]
        if not flat:
            continue
        start = flat[0]["start"]
        end = max(flat[-1]["end"] + 0.12, start + 0.8)                      # minimum on-screen time
        if i + 1 < len(evs) and evs[i + 1] and evs[i + 1][0]:
            end = min(end, evs[i + 1][0][0]["start"] - 0.02) if end > evs[i + 1][0][0]["start"] else end
        parts, t = [], start
        for li, ln in enumerate([l for l in lines_ if l]):
            if li:
                parts.append("\\N")
            for wd in ln:
                k = max(1, int(round((wd["end"] - t) * 100)))
                parts.append(f"{{\\kf{k}}}{wd['word']} ")
                t = wd["end"]
        # lift the caption while an overlay (lower third, callout) occupies the bottom of the frame
        mv = margin_v + int(h * 0.15) if any(a < end and start < b for a, b in (avoid or [])) else 0
        rows.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,{mv},,{{\\fad(60,60)}}{''.join(parts).strip()}")
        timed.append((start, end, " ".join(x["word"] for x in flat)))
    path.write_text(head + "\n".join(rows) + "\n")
    return timed


def write_srt(timed: list[tuple[float, float, str]], path: Path) -> None:
    path.write_text("\n".join(f"{i}\n{_ts(a, False)} --> {_ts(b, False)}\n{txt}\n" for i, (a, b, txt) in enumerate(timed, 1)))


def captions(cut_path: str, w: int, h: int, corrections: dict | None = None, avoid: list | None = None) -> dict:
    cut = Path(cut_path)
    tr = asr.words(cut)
    words = _apply(tr["words"], corrections)
    ass, srt = cut.with_suffix(".ass"), cut.with_suffix(".srt")
    out = cut.with_name(cut.stem + "_captioned.mp4")
    timed = write_ass(words, ass, w, h, avoid)
    write_srt(timed, srt)
    if words:
        ffmpeg("-i", cut, "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "copy", "-movflags", "+faststart", out)
    else:
        out.write_bytes(cut.read_bytes())
    return {"srt": str(srt), "ass": str(ass), "burned_mp4": str(out), "words": len(words), "asr": tr["engine"],
            "transcript": " ".join(w["word"] for w in words), "captions": len(timed)}

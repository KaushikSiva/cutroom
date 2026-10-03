#!/usr/bin/env python3
"""Cutroom worker: picks up films ordered from the website or by remote agents (projects.status = 'queued') and has
Claude Code make them headless with the Cutroom plugin, streaming its narration into the live event feed.

    plugin/server/.venv/bin/python worker/run.py            # loop forever
    plugin/server/.venv/bin/python worker/run.py --once     # take one job and exit
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin" / "server"))

from cutroom import config, db  # noqa: E402
from cutroom.config import log  # noqa: E402

POLL_S = 5
PLUGIN = REPO / "plugin"
LOGS = REPO / "projects" / "_worker_logs"


def prompt_for(p: dict) -> str:
    brief = p.get("brief") or p.get("topic") or ""
    return f"""Use the cutroom make-video skill to make this film from start to finish, then publish it.

a) What: {brief}
b) Aspect ratio: {p.get('aspect_ratio') or '16:9'}
c) Length: about {p.get('length_s') or 60} seconds
d) Style: {p.get('style') or 'calm documentary, narrated like a university professor'}

This project was ordered from the Cutroom website and already exists: call project_start with the brief above and it
will reuse project id {p['id']}. Work autonomously; nobody is available to answer questions, so make reasonable
choices and keep going. {'After the final critique, upscale the final cut to 4K before publishing.' if p.get('want_4k') else 'Do not upscale to 4K.'}
Finish by calling publish.

Work like a professional crew on a deadline: aim to publish within about {max(25, int((p.get('length_s') or 60) / 60 * 12))} minutes.
Use only the Cutroom tools for media: search_footage to find clips, clip_transcript to find the exact seconds of a famous
line, add_clip to download just the section you need, critique to look at anything. Do not download or process videos
yourself with shell commands. Lock the plan after one round of scouting rather than researching every moment
exhaustively, run independent tool calls in parallel, and limit the critique to two rounds."""


def claim() -> dict | None:
    c = db.client()
    if c is None:
        return None
    rows = c.table("projects").select("*").eq("status", "queued").order("created_at").limit(1).execute().data
    if not rows:
        return None
    p = rows[0]
    got = c.table("projects").update({"status": "running", "stage": "brief", "progress": 1}).eq("id", p["id"]).eq("status", "queued").execute().data
    return p if got else None


def run_job(p: dict) -> None:
    pid = p["id"]
    LOGS.mkdir(parents=True, exist_ok=True)
    db.emit(pid, "stage", "a director picked up your film", {"stage": "brief", "progress": 1})
    env = dict(os.environ, CUTROOM_PROJECT_ID=pid, MCP_TOOL_TIMEOUT="1800000", MCP_TIMEOUT="60000")
    key = config.get("ANTHROPIC_API_KEY")
    if key:
        env["ANTHROPIC_API_KEY"] = key
    cmd = ["claude", "-p", prompt_for(p), "--plugin-dir", str(PLUGIN), "--output-format", "stream-json", "--verbose",
           "--permission-mode", "bypassPermissions"]
    log("starting claude for", pid)
    t0 = time.time()
    with open(LOGS / f"{pid}.jsonl", "w") as logf:
        proc = subprocess.Popen(cmd, cwd=str(REPO), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            logf.write(line)
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            relay(pid, ev)
        proc.wait()
    row = db.get_project(pid) or {}
    if row.get("status") != "done":
        db.update(pid, status="failed", error=f"director stopped (exit {proc.returncode}) before publishing")
        db.emit(pid, "error", "the director stopped before publishing", {"exit": proc.returncode})
    log(f"job {pid} finished in {time.time() - t0:.0f}s with status {row.get('status')}")


def relay(pid: str, ev: dict) -> None:
    """Claude's own words become 'thought' events; built-in tool use (Read of a contact sheet, Bash) becomes 'tool'.
    Cutroom MCP tools report themselves, so they're skipped here."""
    if ev.get("type") != "assistant":
        return
    for block in (ev.get("message") or {}).get("content") or []:
        if block.get("type") == "text" and block.get("text", "").strip():
            txt = block["text"].strip()
            db.emit(pid, "thought", txt[:600])
        elif block.get("type") == "tool_use" and not block.get("name", "").startswith("mcp__"):
            inp = block.get("input") or {}
            label = inp.get("file_path") or inp.get("description") or inp.get("command") or ""
            db.emit(pid, "tool", f"{block['name']} {Path(str(label)).name if block['name'] == 'Read' else str(label)[:120]}",
                    {"tool": block["name"], "input": {k: str(v)[:200] for k, v in inp.items()}})


def main():
    once = "--once" in sys.argv
    log("worker up; polling for queued films")
    while True:
        try:
            p = claim()
        except Exception as e:  # noqa: BLE001
            log("poll failed:", repr(e)[:200])
            p = None
        if p:
            try:
                run_job(p)
            except Exception as e:  # noqa: BLE001
                log("job crashed:", repr(e)[:300])
                db.update(p["id"], status="failed", error=str(e)[:300])
            if once:
                return
        else:
            if once:
                log("nothing queued")
                return
            time.sleep(POLL_S)


if __name__ == "__main__":
    main()

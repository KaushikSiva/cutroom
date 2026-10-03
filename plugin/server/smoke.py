"""End-to-end smoke test of the Cutroom tools: a 3-shot, ~15 s film through every stage, using real providers where keys
exist and fallbacks where they don't.  Run:  .venv/bin/python smoke.py [--no-footage] [--no-graphics] [--upscale]"""
import asyncio
import json
import sys
import time

from cutroom import server as S

ARGS = set(sys.argv[1:])


def step(name):
    print(f"\n=== {name}  ({time.strftime('%H:%M:%S')})", flush=True)


async def main():
    t0 = time.time()
    step("project_start")
    p = await S.project_start("A short explainer on why data centres are built near rivers", "16:9", 15,
                              "calm documentary, dusk light, restrained palette")
    pid = p["project_id"]
    print(p)

    plan = {
        "title": "Rivers and Racks", "logline": "Why the cloud lives by the water.",
        "references": [{"name": "hall", "prompt": "a vast data centre hall, cool blue light, rows of server racks, cinematic"}],
        "shots": [
            {"id": "s01", "kind": "graphic", "duration_s": 4, "engine": "hyperframes",
             "narration": "Every search you make ends its journey in a building like this one.",
             "direction": "measured and warm, like a university professor opening a lecture", "visual": "title card"},
            {"id": "s02", "kind": "footage", "duration_s": 5, "youtube_query": "data center aerial drone",
             "narration": "Engineers place them beside rivers, because cooling is the quiet problem behind every computer.",
             "direction": "thoughtful, slightly slower on 'quiet problem'", "visual": "aerial footage of a data centre", "label": "Huntsville, Alabama"},
            {"id": "s03", "kind": "generated", "duration_s": 6, "refs": ["hall"], "transition": "dissolve",
             "narration": "Water carries the heat away, and the river, in a sense, becomes part of the machine.",
             "direction": "gentle, reflective, a small pause before the last clause", "visual": "slow push down a server aisle, blue light"},
        ],
    }
    step("save_plan"); print(await S.save_plan(pid, plan))
    step("gen_reference"); print(await S.gen_reference(pid, "hall", plan["references"][0]["prompt"]))
    step("gen_keyframe s03"); print(await S.gen_keyframe(pid, "s03", "a long server aisle in cool blue light, low angle, cinematic", ["hall"]))
    step("gen_keyframe s02"); print(await S.gen_keyframe(pid, "s02", "aerial view of a data centre beside a river at dusk"))
    step("voiceover")
    print(json.dumps(await S.voiceover(pid, [{"shot_id": s["id"], "text": s["narration"], "direction": s["direction"]} for s in plan["shots"]]), indent=1))
    step("music (background)"); print(await S.music(pid, "restrained documentary score, felt piano and low strings, 80 bpm", 20))
    step("render_animatic"); a = await S.render_animatic(pid); print(a)
    if "--no-graphics" not in ARGS:
        step("motion_graphic title + lower third")
        for kw in ({"shot_id": "s01", "engine": "hyperframes", "template": "title_card", "params": {"title": "Rivers and Racks", "subtitle": "Why the cloud lives by the water"}},
                   {"shot_id": "s02", "engine": "hyperframes", "template": "lower_third", "params": {"name": "Huntsville, Alabama", "role": "Data centre, 2023"}}):
            try:
                print(await S.motion_graphic(pid, **kw))
            except Exception as e:  # noqa: BLE001
                print("motion graphic failed (assemble falls back to a card):", repr(e)[:300])
    if "--no-footage" not in ARGS:
        step("search_footage + add_clip")
        c = await S.search_footage(pid, "data center drone flyover", 3, "s02")
        best = c["candidates"][0]
        print(best["id"], best["title"], best.get("rank"))
        print(await S.add_clip(pid, best["id"], 20, 26, "s02"))
    step("gen_shot s03"); print(await S.gen_shot(pid, "s03", "the camera glides slowly down the aisle", duration_s=6))
    step("assemble final"); cut = await S.assemble(pid, "final"); print({k: v for k, v in cut.items() if k != "layout"})
    step("captions"); cp = await S.captions(pid, cut["mp4_path"], {"centres": "centres"}); print({k: v for k, v in cp.items() if k != "transcript"})
    step("critique"); cr = await S.critique(pid, cp["burned_mp4"])
    print(json.dumps({k: cr[k] for k in ("script_match", "metrics", "narration_style", "issues", "contact_sheets", "asr")}, indent=1)[:3000])
    final = cp["burned_mp4"]
    if "--upscale" in ARGS:
        step("upscale_4k"); u = await S.upscale_4k(pid, final); print(u); final = u["path"]
    step("publish"); print(await S.publish(pid, cp["burned_mp4"], "Rivers and Racks", "Why the cloud lives by the water."))
    print(f"\nDONE in {time.time() - t0:.0f}s · project {pid}")


asyncio.run(main())

"""Render one sample from every engine/template in 16:9 and 9:16 into /tmp/cutroom-motion-test and print timings.

    cd plugin/server && python3 -m cutroom.motion.selftest [--only hyperframes,manim] [--aspect 16x9]
"""
import argparse
import concurrent.futures as cf
import os
import time

from . import render
from .common import frame_png

OUT = "/tmp/cutroom-motion-test"
SAMPLES = [
    ("hyperframes", "title_card", {"kicker": "Chapter one", "title": "The Rise of the Neoclouds", "subtitle": "How a handful of GPU landlords rewired the economics of AI compute"}),
    ("hyperframes", "lower_third", {"name": "Michael Intrator", "role": "Chief executive, CoreWeave"}),
    ("hyperframes", "data_callout", {"title": "Contracted backlog", "value": 55.6, "prefix": "$", "suffix": "B", "label": "Revenue already signed with AI labs, most of it with a single customer",
                                     "bars": [{"label": "OpenAI", "value": 22.4}, {"label": "Microsoft", "value": 18.1}, {"label": "Meta", "value": 14.2}, {"label": "Other", "value": 0.9}]}),
    ("hyperframes", "kinetic_quote", {"quote": "Compute is the new oil, and everyone is short of it.", "author": "Industry analyst", "emphasis": ["compute", "oil"]}),
    ("manim", "bar_chart", {"title": "GPU cloud revenue, 2026 (USD billions)", "unit": "B", "highlight": 0,
                            "data": [{"label": "CoreWeave", "value": 11.2}, {"label": "Lambda", "value": 3.1}, {"label": "Crusoe", "value": 2.4}, {"label": "Nebius", "value": 2.9}]}),
    ("manim", "line_chart", {"title": "H100 rental price per hour", "x": [2023, 2024, 2025, 2026], "series": [{"name": "On-demand", "y": [8.0, 4.5, 2.9, 2.1]}, {"name": "Reserved", "y": [4.0, 2.8, 2.0, 1.6]}]}),
    ("manim", "process", {"title": "How a neocloud makes money", "steps": ["Raise debt", "Buy GPUs", "Sign take-or-pay", "Rent capacity"]}),
    ("motion_canvas", "network", {"title": "Who rents the GPUs", "center": "Neocloud", "nodes": ["OpenAI", "Mistral", "Startups", "Enterprises", "Research labs"]}),
    ("motion_canvas", "flow", {"title": "From chip to token", "steps": ["Nvidia ships H200s", "Neocloud racks them", "Lab rents capacity", "Model serves users"]}),
    ("blender", "title_card", {"kicker": "A Cutroom film", "title": "The Rise of the Neoclouds", "subtitle": "How GPU landlords rewired the economics of AI"}),
    ("blender", "lower_third", {"name": "Michael Intrator", "role": "CEO, CoreWeave"}),
    ("blender", "map_route", {"title": "Where the GPUs live", "places": [{"name": "Roseland, NJ", "lat": 40.82, "lon": -74.3}, {"name": "Plano, TX", "lat": 33.0, "lon": -96.7},
                                                                       {"name": "Hillsboro, OR", "lat": 45.52, "lon": -122.99}]}),
    ("blender", "timeline", {"title": "From crypto miner to AI cloud", "events": [{"date": "2017", "label": "Mining Ethereum in a garage"}, {"date": "2019", "label": "Pivot to GPU cloud"},
                                                                                {"date": "2023", "label": "Nvidia invests"}, {"date": "2025", "label": "IPO on Nasdaq"}]}),
]
OVERLAYS = {"lower_third"}
ASPECTS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def one(engine, template, params, aspect):
    w, h = ASPECTS[aspect]
    ext = ".mov" if template in OVERLAYS else ".mp4"
    out = os.path.join(OUT, f"{engine}_{template}_{aspect}{ext}")
    t0 = time.time()
    try:
        r = render(engine, out, w, h, template=template, params=params)
        frame_png(r["path"], max(0.1, r["duration"] - 0.4), out.rsplit(".", 1)[0] + ".png")
        return engine, template, aspect, round(time.time() - t0, 1), "ok", r["duration"]
    except Exception as err:  # noqa: BLE001
        return engine, template, aspect, round(time.time() - t0, 1), "FAIL " + str(err)[-300:], 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--aspect", default="16x9,9x16")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    jobs = [(e, t, p, asp) for e, t, p in SAMPLES if not only or e in only for asp in a.aspect.split(",")]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for engine, template, aspect, secs, status, dur in ex.map(lambda j: one(*j), jobs):
            print(f"{engine:14s} {template:14s} {aspect:5s} {secs:7.1f}s  dur {dur:5.2f}s  {status}", flush=True)


if __name__ == "__main__":
    main()

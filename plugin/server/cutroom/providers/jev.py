"""Jev (TypeSafe System One): fast typed decisions with calibrated confidence. Every function returns None when
TYPESAFE_API_KEY is unset or the call fails, and callers then leave the decision to Claude."""
from .. import config
from ..config import log

ENGINES = {
    "generated_motion": "AI video for a shot with strong physical motion: people moving, vehicles, water, crowds, camera flying through a scene",
    "generated_still": "AI video for a mostly static or slow cinematic shot: a landscape, a portrait, an object, a slow push-in",
    "footage": "Real archival or documentary footage of real events, places or people that exist and were filmed",
    "hyperframes": "Web-style motion graphic: animated text, UI, cards, data callouts, kinetic typography",
    "manim": "Mathematical or technical diagram: equations, graphs, plots, geometry, step-by-step explanations",
    "motion_canvas": "Code-driven 2D animation: flow diagrams, architecture boxes and arrows, process animations",
    "blender": "3D title card, map with a route between places, or a timeline of dated events",
}


def _client():
    key = config.get("TYPESAFE_API_KEY")
    if not key:
        return None
    from typesafe_sdk import TypeSafeClient
    return TypeSafeClient(api_key=key, model=config.get("CUTROOM_JEV_MODEL"))


def route_shot(shot: dict) -> dict | None:
    """-> {engine, confidence, probabilities}"""
    try:
        c = _client()
        if not c:
            return None
        from typesafe_sdk import Choice
        with c:
            r = c.system_one(state={"shot": {k: shot.get(k) for k in ("visual", "narration", "kind", "motion")}},
                             questions={"engine": Choice(instructions="Which production method best makes this documentary shot?",
                                                         criteria=ENGINES)})
        a = r.choices["engine"]
        return {"engine": a.choice, "confidence": a.confidence, "probabilities": dict(a.probabilities)}
    except Exception as e:  # noqa: BLE001
        log("jev route_shot failed", repr(e)[:300])
        return None


def rank_footage(shot_text: str, candidates: list[dict]) -> list[dict] | None:
    """Scores each candidate (title, channel, description) for how well it can illustrate the shot. -> [{id, score, confidence}]"""
    try:
        c = _client()
        if not c or not candidates:
            return None
        from typesafe_sdk import Score
        qs = {f"c{i}": Score(instructions={"task": "How well could footage from this video illustrate the shot?", "shot": shot_text,
                                           "video": {"title": cand.get("title"), "channel": cand.get("channel"), "description": cand.get("description"),
                                                     "chapters": [c.get("title") for c in cand.get("chapters") or []][:15]}},
                             criteria=["unrelated", "loosely related", "relevant", "an excellent match"])
              for i, cand in enumerate(candidates)}
        with c:
            r = c.system_one(state={"shot": shot_text}, questions=qs)
        return [{"id": cand["id"], "score": r.scores[f"c{i}"].score, "confidence": r.scores[f"c{i}"].confidence}
                for i, cand in enumerate(candidates)]
    except Exception as e:  # noqa: BLE001
        log("jev rank_footage failed", repr(e)[:300])
        return None


def judge_narration(text: str) -> dict | None:
    """Checks the narration against the house style: a university professor, not chatbot copy."""
    try:
        c = _client()
        if not c or not text.strip():
            return None
        from typesafe_sdk import Noul, Score
        with c:
            r = c.system_one(state={"narration": text}, questions={
                "punchy": Noul(instructions="The narration relies on short, punchy, fragmentary sentences for effect (for example 'Fast. Cheap. Everywhere.')"),
                "numbers": Noul(instructions="The narration is crowded with statistics and numbers, more than one figure in most sentences"),
                "cliche": Noul(instructions="The narration uses marketing or chatbot clichés such as 'game-changer', 'in a world where', 'let's dive in', 'here's the thing'"),
                "professor": Score(instructions="How much does this read like a thoughtful university professor explaining the subject in flowing, connected prose?",
                                   criteria=["not at all", "somewhat", "mostly", "exactly"]),
            })
        return {"punchy": r.nouls["punchy"].noul, "numbers": r.nouls["numbers"].noul, "cliche": r.nouls["cliche"].noul,
                "professor": r.scores["professor"].score, "professor_confidence": r.scores["professor"].confidence}
    except Exception as e:  # noqa: BLE001
        log("jev judge_narration failed", repr(e)[:300])
        return None

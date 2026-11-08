"""Compare candidates with a HUMAN gold set: promos a person picked by hand.

The gold file is written only by a person (template: docs/gold_promos.template.json,
local copy: data/config/gold_promos.json, which Git ignores). Code never fills it in.

Measures:
  recall        share of gold picks covered by some candidate in the same episode
                (the candidate contains at least half of the gold clip)
  hook_aligned  share of gold picks with a candidate starting within 3 s of the gold start
  baseline      the same recall for randomly chosen valid windows, using the same number
                of candidates per episode (fixed seed, averaged over many trials).
                If the rules do not beat random, they are not helping.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from engine.screenplay.timestamps import parse_timestamp

COVER_THRESHOLD = 0.5
HOOK_TOLERANCE_S = 3.0
BASELINE_TRIALS = 200
BASELINE_SEED = 20261108


def load_gold(path: Optional[str | Path]) -> Optional[dict]:
    if path is None or not Path(path).exists():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _time(value) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return parse_timestamp(value)
    return None


def parse_picks(gold: dict) -> tuple[list[dict], list[dict]]:
    """Return (usable picks, problems). A pick uses its first segment for Stage 2 matching."""
    picks, problems = [], []
    for i, raw in enumerate(gold.get("promos") or []):
        segments = raw.get("segments") or []
        first = segments[0] if segments else {}
        start, end = _time(first.get("start")), _time(first.get("end"))
        if not first.get("episode_id") or start is None or end is None or end <= start:
            problems.append({"index": i, "id": raw.get("id"), "problem": "needs segments[0] with episode_id, start < end (MM:SS.ss)"})
            continue
        picks.append({"id": raw.get("id") or f"G{i + 1:02d}", "episode_id": first["episode_id"],
                      "start": start, "end": end, "multi_segment": len(segments) > 1})
    return picks, problems


def _covers(c_start, c_end, g_start, g_end) -> bool:
    shared = min(c_end, g_end) - max(c_start, g_start)
    return shared > 0 and shared / (g_end - g_start) >= COVER_THRESHOLD


def evaluate_gold(gold: Optional[dict], records: list[dict], windows_by_episode: dict, per_episode: int) -> dict:
    if gold is None:
        return {"status": "not_provided",
                "how": "Copy docs/gold_promos.template.json to data/config/gold_promos.json and add 10-15 picks by hand."}
    picks, problems = parse_picks(gold)
    if not picks:
        return {"status": "empty", "problems": problems}

    spans = {}
    for r in records:
        seg = r["segments"][0]
        spans.setdefault(r["episode_id"], []).append((seg["start_s"], seg["end_s"], r["id"]))

    details, covered, aligned = [], 0, 0
    for p in picks:
        mine = spans.get(p["episode_id"], [])
        hit = next((cid for s, e, cid in mine if _covers(s, e, p["start"], p["end"])), None)
        near = next((cid for s, e, cid in mine if abs(s - p["start"]) <= HOOK_TOLERANCE_S), None)
        covered += hit is not None
        aligned += near is not None
        details.append({"id": p["id"], "episode_id": p["episode_id"], "covered_by": hit, "hook_aligned_with": near,
                        "multi_segment_first_only": p["multi_segment"]})

    # random baseline with the same per-episode budget as the rules actually used
    budget = {eid: len(v) for eid, v in spans.items()}
    rng = random.Random(BASELINE_SEED)
    total = 0.0
    for _ in range(BASELINE_TRIALS):
        hits = 0
        for p in picks:
            pool = windows_by_episode.get(p["episode_id"], [])
            k = min(len(pool), budget.get(p["episode_id"], per_episode))
            sample = rng.sample(pool, k) if k else []
            hits += any(_covers(w.start.t, w.end.t, p["start"], p["end"]) for w in sample)
        total += hits / len(picks)

    n = len(picks)
    return {
        "status": "evaluated",
        "picks": n,
        "recall": round(covered / n, 4),
        "hook_aligned": round(aligned / n, 4),
        "random_baseline_recall": round(total / BASELINE_TRIALS, 4),
        "baseline": {"trials": BASELINE_TRIALS, "seed": BASELINE_SEED, "budget": "same number of candidates per episode"},
        "problems": problems,
        "details": details,
    }

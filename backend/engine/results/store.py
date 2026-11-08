"""Serve processed outputs (show.json, promos.json, judge_report.json) to the UI.

Read-only by design: the pipeline runs from the command line, the UI only displays.
Slugs and promo IDs are checked against strict patterns before touching the disk,
so a request can never reach a path outside data/processed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from engine.screenplay.timestamps import format_timestamp as ts

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
PROMO_ID = re.compile(r"^E[0-9A-Z]{1,5}-W\d{5}-\d{5}$")
TOL = 0.011


class ResultNotFound(LookupError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _read(path: Path) -> Optional[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _show_dir(data_dir: Path, slug: str) -> Path:
    if not SLUG.match(slug or ""):
        raise ResultNotFound("invalid_slug", "Show names contain only lowercase letters, digits and hyphens.")
    folder = Path(data_dir) / "processed" / slug
    if not (folder / "show.json").exists():
        raise ResultNotFound("show_not_found", f"No parsed show called {slug!r}. Run parse_show first.")
    return folder


def list_shows(data_dir: Path) -> list[dict]:
    root = Path(data_dir) / "processed"
    shows = []
    for folder in sorted(root.iterdir()) if root.exists() else []:
        if not (folder.is_dir() and SLUG.match(folder.name) and (folder / "show.json").exists()):
            continue
        promos = _read(folder / "promos.json")
        with (folder / "show.json").open(encoding="utf-8") as fh:
            show = json.load(fh)
        shows.append({
            "slug": folder.name,
            "title": show.get("show", {}).get("title", folder.name),
            "episodes": len(show.get("episodes", [])),
            "has_candidates": (folder / "candidates.json").exists(),
            "has_promos": promos is not None,
            "provider": promos.get("provider") if promos else None,
            "model": promos.get("model") if promos else None,
            "is_mock": bool(promos and promos.get("provider") == "mock"),
        })
    return shows


def _promo_row(p: dict) -> dict:
    seg = p["segments"][0]
    ai = p.get("ai") or {}
    return {
        "id": p["id"], "rank": p["rank"], "post_first_rank": p.get("post_first_rank"), "episode_id": p["episode_id"],
        "start": seg["start_raw"], "end": seg["end_raw"], "start_s": seg["start_s"], "end_s": seg["end_s"],
        "duration_s": p["duration_s"], "final_score": p.get("final_score"), "rule_score": p["rule_score"],
        "rule_rank": p.get("rule_rank"), "ai_score": p.get("ai_score"), "judged": p.get("judged", False),
        "verdict": ai.get("verdict"), "hook": ai.get("hook"), "cliffhanger": ai.get("cliffhanger"), "why": ai.get("why"),
        "scores": {k: ai.get(f"{k}_score") for k in ("hook", "cliffhanger", "standalone")} if ai else None,
        "trimmed": bool(p.get("trim", {}).get("applied")), "flags": p.get("flags", []),
    }


def show_results(data_dir: Path, slug: str) -> dict:
    folder = _show_dir(data_dir, slug)
    promos = _read(folder / "promos.json")
    if promos is None:
        hint = "Run judge_promos." if (folder / "candidates.json").exists() else "Run find_candidates, then judge_promos."
        raise ResultNotFound("not_judged", f"No ranked promos for {slug!r} yet. {hint}")
    report = _read(folder / "judge_report.json") or {}
    rows = [_promo_row(p) for p in promos["promos"]]
    return {
        "show": {"slug": slug, "title": promos.get("show", {}).get("title", slug)},
        "run": {"provider": promos.get("provider"), "model": promos.get("model"), "is_mock": promos.get("provider") == "mock",
                "prompt_version": promos.get("prompt_version"), "judge_config_version": promos.get("judge_config_version")},
        "counts": report.get("counts", {}),
        "failed_episodes": report.get("calls", {}).get("failed_episodes", []),
        "post_first": [r["id"] for r in sorted((r for r in rows if r["post_first_rank"]), key=lambda r: r["post_first_rank"])],
        "episodes": sorted({r["episode_id"] for r in rows}),
        "promos": rows,
        "csv_available": (folder / "promos.csv").exists(),
    }


def clip_detail(data_dir: Path, slug: str, promo_id: str) -> dict:
    if not PROMO_ID.match(promo_id or ""):
        raise ResultNotFound("invalid_promo_id", "Promo IDs look like E001-W01130-04580.")
    folder = _show_dir(data_dir, slug)
    promos = _read(folder / "promos.json") or {"promos": []}
    promo = next((p for p in promos["promos"] if p["id"] == promo_id), None)
    if promo is None:
        raise ResultNotFound("promo_not_found", f"No promo {promo_id} in {slug!r}.")
    seg = promo["segments"][0]
    with (folder / "show.json").open(encoding="utf-8") as fh:
        show = json.load(fh)
    episode = next(e for e in show["episodes"] if e["id"] == seg["episode_id"])
    a, b = seg["start_s"], seg["end_s"]
    lines = []
    for scene in episode["scenes"]:
        for bl in scene["blocks"]:
            if bl["start_s"] is None or not (bl["start_s"] < b - TOL and bl["end_s"] > a + TOL):
                continue
            label = bl["kind"].upper() if bl["kind"] != "dialogue" else (bl.get("speaker") or "?") + \
                (f" [{bl['voice']}]" if bl.get("voice") else "") + (f" ({bl['delivery']})" if bl.get("delivery") else "")
            lines.append({"id": bl["id"], "kind": bl["kind"], "label": label, "start": ts(bl["start_s"]), "end": ts(bl["end_s"]),
                          "start_s": bl["start_s"], "text": bl["text"], "partial": bl["start_s"] < a - TOL or bl["end_s"] > b + TOL})
    lines.sort(key=lambda x: (x["start_s"], x["id"]))
    trim = promo.get("trim", {})
    return {"promo": _promo_row(promo), "lines": lines,
            "original": ({"start": trim["original"]["start_raw"], "end": trim["original"]["end_raw"]} if trim.get("applied") else None)}


def csv_path(data_dir: Path, slug: str) -> Path:
    path = _show_dir(data_dir, slug) / "promos.csv"
    if not path.exists():
        raise ResultNotFound("not_judged", "No promos.csv yet. Run judge_promos.")
    return path

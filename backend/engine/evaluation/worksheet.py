"""Build the human annotation kit from show.json ONLY:

    gold_worksheet.md   readable per-episode guide (loglines, scenes, every spoken line with
                        times) plus a blank pick log
    gold_promos.json    blank gold file in the agreed schema (never overwritten once it exists)

This module deliberately never reads candidates.json or any score. The human picks
are the yardstick for the rules, so they must not be steered by the rules.

    python -m engine.evaluation.worksheet <show.json | folder> [--config-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from engine.screenplay.timestamps import format_timestamp as ts

PICK_SLOTS = 15

INSTRUCTIONS = [
    "Pick 10-15 promos YOU would post. Decide them from this worksheet or by watching the show, BEFORE opening candidates_review.md.",
    "Each pick is one continuous 20-60 s stretch from one episode: a hook in the first 3 s, an unresolved cut at the end, understandable by a stranger.",
    "Spread picks over at least 6 different episodes, and make at least 3 that do NOT end at an episode's final line.",
    "Times come from the worksheet (MM:SS.ss, episode-relative). Approximate is fine: a pick counts as found if a candidate covers at least half of it.",
    "Copy blank_pick into promos once per pick, change every placeholder, keep commas between entries and none after the last.",
    "Fill labeler and method (for example: read scripts of E001-E025, about 40 minutes). This file stays in data/config, which Git ignores.",
]

BLANK_PICK = {
    "id": "G01",
    "segments": [{"episode_id": "E0NN", "start": "MM:SS.ss", "end": "MM:SS.ss"}],
    "hook": "what stops a scrolling viewer in the first 3 s",
    "cliffhanger": "what is left unresolved at the cut",
    "why": "one line on why you would post it",
    "confidence": "high | medium | low",
}


def blank_gold(show_doc: dict) -> dict:
    return {
        "schema_version": 1,
        "show_slug": show_doc.get("show", {}).get("slug", ""),
        "labeler": "",
        "labeled_on": "",
        "method": "",
        "instructions": INSTRUCTIONS,
        "blank_pick": BLANK_PICK,
        "promos": [],
    }


def _line(block: dict) -> str:
    who = block.get("speaker") or "?"
    if block.get("voice"):
        who += f" [{block['voice']}]"
    if block.get("delivery"):
        who += f" ({block['delivery']})"
    text = block.get("text", "").replace("\n", " / ")
    return f"| {ts(block.get('start_s'))} | {ts(block.get('end_s'))} | {who} | {text} |"


def build_worksheet(show_doc: dict) -> str:
    title = show_doc.get("show", {}).get("title", "")
    episodes = show_doc["episodes"]
    out = [
        f"# Gold-set worksheet: {title}",
        "",
        "This worksheet is built from the parsed screenplay only. It contains no candidates or scores, on purpose.",
        "Do not open candidates_review.md until your picks are written down.",
        "",
        "## How to pick",
        "",
        *[f"{i}. {text}" for i, text in enumerate(INSTRUCTIONS, start=1)],
        "",
        "## Pick log",
        "",
        "Draft here, then copy into data/config/gold_promos.json.",
        "",
        "| Pick | Episode | Start | End | Length | Hook (first 3 s) | Cliffhanger (at the cut) | Why | Confidence |",
        "|---|---|---|---|---|---|---|---|---|",
        *[f"| G{i:02d} |  |  |  |  |  |  |  |  |" for i in range(1, PICK_SLOTS + 1)],
        "",
        "## Episodes",
        "",
        "Every spoken line with its times. Camera, action and sound beats are in "
        "data/processed/<show-slug>/episodes/E0NN.txt if you need exact cut points.",
    ]
    for ep in episodes:
        out += ["", f"### {ep['id']}  ({ts(ep.get('duration_s'))})"]
        if ep.get("logline"):
            out += ["", f"Logline: {ep['logline']}"]
        for scene in ep["scenes"]:
            out += ["", f"**{scene['id']}** {scene.get('heading') or ''} ({ts(scene.get('start_s'))}-{ts(scene.get('end_s'))})", ""]
            lines = [b for b in scene["blocks"] if b["kind"] == "dialogue"]
            if lines:
                out += ["| Start | End | Speaker | Line |", "|---|---|---|---|", *[_line(b) for b in lines]]
            else:
                out.append("(no dialogue)")
        out += ["", "Moments I noticed:", ""]
    return "\n".join(out) + "\n"


def write_kit(show_doc: dict, config_dir: Path) -> dict:
    """Write the worksheet (regenerated each time) and the gold file (only if it does not exist yet)."""
    config_dir.mkdir(parents=True, exist_ok=True)
    worksheet = config_dir / "gold_worksheet.md"
    worksheet.write_text(build_worksheet(show_doc), encoding="utf-8")
    gold = config_dir / "gold_promos.json"
    if gold.exists():
        status = "kept existing file (your picks are never overwritten)"
    else:
        gold.write_text(json.dumps(blank_gold(show_doc), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        status = "created blank file"
    return {"worksheet": worksheet, "gold": gold, "gold_status": status}


def run(argv: Optional[list[str]] = None) -> int:
    from engine.screenplay.cli import default_data_dir

    parser = argparse.ArgumentParser(prog="worksheet", description="Create the gold-set worksheet and blank gold file.")
    parser.add_argument("show", help="show.json or the folder that contains it")
    parser.add_argument("--config-dir", help="where to write (default: <data>/config)")
    args = parser.parse_args(argv)
    path = Path(args.show)
    path = path / "show.json" if path.is_dir() else path
    try:
        show_doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    result = write_kit(show_doc, Path(args.config_dir) if args.config_dir else default_data_dir() / "config")
    print(f"Worksheet:  {result['worksheet']}\nGold file:  {result['gold']} ({result['gold_status']})")
    return 0


if __name__ == "__main__":
    sys.exit(run())

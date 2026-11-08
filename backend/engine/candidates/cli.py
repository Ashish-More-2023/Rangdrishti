"""python -m engine.candidates <show.json | folder> [--config FILE] [--out DIR] [--gold FILE]

Also used by `python manage.py find_candidates`.
Exit codes: 0 ok, 1 some window or candidate failed a hard rule, 2 bad input or config.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from engine.evaluation.gold import load_gold
from engine.screenplay.cli import default_data_dir

from .config import ConfigError, load_config
from .pipeline import find_candidates, write_outputs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="find_candidates", description="Find rule-based promo candidates in a parsed show.")
    p.add_argument("show", help="show.json from parse_show, or the folder that contains it")
    p.add_argument("--config", help="candidates config JSON (default: the versioned one in engine/candidates)")
    p.add_argument("--out", help="output folder (default: the folder containing show.json)")
    p.add_argument("--gold", help="human gold set (default: <data>/config/gold_promos.json if present)")
    return p


def resolve_show_path(arg: str) -> Path:
    path = Path(arg)
    return path / "show.json" if path.is_dir() else path


def summary(result, out_dir: Path, seconds: float) -> str:
    r = result.report
    c, v, e = r["counts"], r["validation"], r["episode_endings"]
    s = r["scores"]["selected"]
    rows = [
        f"Episodes:     {c['episodes_processed']} processed, {len(c['episodes_skipped'])} skipped",
        f"Cut points:   {r['cut_points'].get('boundaries', 0)} boundaries, {r['cut_points'].get('clean', 0)} clean",
        f"Windows:      {c['valid_windows']} valid (20-60 s, clean cuts)",
        f"Selected:     {c['selected']} candidates  per-episode counts {c['episodes_by_selected_count']}",
        f"Scores:       selected median {s.get('median')} (min {s.get('min')}, max {s.get('max')})",
        f"Endings:      {e['selected_ending_in_zone']} selected end at an episode ending",
        f"Validation:   {v['windows_failing']} of {v['windows_checked']} windows fail, "
        f"{len(v['selected_failing'])} of {v['selected_checked']} candidates fail",
        f"Gold set:     {r['gold']['status']}",
        f"Runtime:      {seconds:.2f}s",
        f"Output:       {out_dir}",
    ]
    return "\n".join(rows)


def run(argv: Optional[list[str]] = None, data_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    data_dir = Path(data_dir) if data_dir else default_data_dir()
    show_path = resolve_show_path(args.show)
    try:
        show_doc = json.loads(show_path.read_text(encoding="utf-8"))
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: {show_path.resolve()} not found. Run parse_show first.", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    gold_path = Path(args.gold) if args.gold else data_dir / "config" / "gold_promos.json"
    started = time.perf_counter()
    try:
        result = find_candidates(show_doc, config, load_gold(gold_path))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    seconds = time.perf_counter() - started

    out_dir = Path(args.out) if args.out else show_path.parent
    write_outputs(result, out_dir)
    print(summary(result, out_dir, seconds))
    v = result.report["validation"]
    return 1 if v["windows_failing"] or v["selected_failing"] else 0

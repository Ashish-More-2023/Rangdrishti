"""Command-line entry point: python -m engine.screenplay <pack> [--out DIR] [--aliases FILE]

Also used by `python manage.py parse_show`. Exit code 1 when the parse has errors,
so scripts and CI can stop on bad input; outputs are still written for inspection.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .pipeline import parse_show, write_outputs

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_data_dir() -> Path:
    return Path(os.getenv("RANGDRISHTI_DATA_DIR") or REPO_ROOT / "data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parse_show", description="Parse a screenplay pack into structured JSON.")
    parser.add_argument("pack", help="Folder or .zip containing the episode .txt files")
    parser.add_argument("--out", help="Output folder (default: <data>/processed/<show-slug>)")
    parser.add_argument("--aliases", help="speaker_aliases.json (default: <data>/config/speaker_aliases.json if present)")
    return parser


def summary(result, out_dir: Path) -> str:
    counts, lines, issues = result.report["counts"], result.report["lines"], result.report["issues"]
    rows = [
        f"Show:        {result.show.title}",
        f"Episodes:    {counts['episodes']}",
        f"Scenes:      {counts['scenes']}",
        f"Blocks:      {counts['blocks']}  {counts['blocks_by_kind']}",
        f"Lines:       {lines['non_blank']} non-blank, {lines['unaccounted']} unaccounted",
        f"Issues:      {issues['errors']} errors, {issues['warnings']} warnings, {issues['info']} info",
        f"Output:      {out_dir}",
    ]
    for item in [i for i in issues["items"] if i["severity"] == "error"][:10]:
        rows.append(f"  ERROR {item['code']} {item['file']}:{item['line']} {item['message']}")
    return "\n".join(rows)


def run(argv: Optional[list[str]] = None, data_dir: Optional[Path] = None) -> int:
    args = build_parser().parse_args(argv)
    data_dir = Path(data_dir) if data_dir else default_data_dir()

    aliases = args.aliases
    default_aliases = data_dir / "config" / "speaker_aliases.json"
    if aliases is None and default_aliases.exists():
        aliases = default_aliases

    try:
        result = parse_show(args.pack, aliases)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else data_dir / "processed" / result.show.slug
    write_outputs(result, out_dir)
    print(summary(result, out_dir))
    return 1 if result.error_count else 0

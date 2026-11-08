"""python -m engine.judge <processed show folder> [--provider P] [--model M] [--episodes E001,E002]
                         [--max-calls N] [--refresh] [--list-models]

Reads show.json + candidates.json from the folder, writes promos.json, promos.csv and
judge_report.json there, and raw model responses to data/raw_outputs/<slug>/<provider-model>/.
Exit codes: 0 ok, 1 some episodes failed (rule-only fallback used), 2 setup problem.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from engine.ai import ProviderError, provider_from_env
from engine.screenplay.cli import REPO_ROOT, default_data_dir

from .pipeline import judge_show, load_judge_config, raw_dir_for, write_outputs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="judge_promos", description="AI-judge the rule-based promo candidates.")
    p.add_argument("folder", nargs="?", help="processed show folder containing show.json and candidates.json")
    p.add_argument("--provider", help="gemini | openai_compatible | mock (default: LLM_PROVIDER or mock)")
    p.add_argument("--model", help="override LLM_MODEL")
    p.add_argument("--episodes", help="comma-separated episode IDs to judge (default: all)")
    p.add_argument("--max-calls", type=int, help="stop after this many new API calls (cache still used)")
    p.add_argument("--refresh", action="store_true", help="ignore cached responses and call the model again")
    p.add_argument("--config", help="judge config JSON (default: engine/judge/judge_config.json)")
    p.add_argument("--list-models", action="store_true", help="list the models your key can use, then exit")
    return p


def run(argv: Optional[list[str]] = None, data_dir: Optional[Path] = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = build_parser().parse_args(argv)
    data_dir = Path(data_dir) if data_dir else default_data_dir()
    try:
        provider = provider_from_env(args.provider, args.model)
        if args.list_models:
            if not hasattr(provider, "list_models"):
                print("The mock provider has no models to list.")
                return 0
            print("\n".join(provider.list_models()))
            return 0
        if not args.folder:
            print("Error: give the processed show folder.", file=sys.stderr)
            return 2
        folder = Path(args.folder)
        show_doc = json.loads((folder / "show.json").read_text(encoding="utf-8"))
        candidates_doc = json.loads((folder / "candidates.json").read_text(encoding="utf-8"))
        config = load_judge_config(args.config)
    except ProviderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    episodes = {e.strip() for e in args.episodes.split(",")} if args.episodes else None
    raw_dir = raw_dir_for(data_dir, candidates_doc["show"]["slug"], provider)
    started = time.perf_counter()
    result = judge_show(show_doc, candidates_doc, provider, config, raw_dir, episodes, args.refresh, args.max_calls)
    write_outputs(result, folder)
    r = result.report
    print(f"Provider:    {r['provider']} / {r['model']}" + ("   (MOCK: placeholder scores)" if r["mock_warning"] else ""))
    print(f"Episodes:    {r['calls']['by_status']}")
    print(f"Candidates:  {r['counts']['judged']} judged, {r['counts']['unjudged']} unjudged; verdicts {r['counts']['verdicts']}")
    print(f"Trims:       {r['trims']}")
    print(f"Parse:       {r['parse_issues']['by_code'] or 'no issues'}")
    print(f"Validation:  {len(r['validation']['promos_failing'])} of {r['validation']['promos_checked']} promos fail hard rules")
    print(f"Post first:  {r['counts']['post_first']} promos")
    print(f"Runtime:     {time.perf_counter() - started:.1f}s")
    print(f"Output:      {folder}  |  raw responses: {raw_dir}")
    if result.failed_episodes:
        print(f"FAILED:      {', '.join(result.failed_episodes)} (rule-only fallback; re-run to retry, cached ones are free)")
        return 1
    return 0

"""Run Stage 2 end to end on a parsed show.json:
cuts -> windows -> features/score -> per-episode selection -> show-wide rank -> validation -> outputs.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.evaluation.gold import evaluate_gold
from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig, validate_promo

from .config import config_hash
from .features import Vocabulary
from .render import candidate_record, review_markdown
from .report import distribution, feature_means
from .scoring import EpisodeScorer
from .select import select_for_episode
from .timeline import find_cuts
from .windows import enumerate_windows

CANDIDATES_SCHEMA_VERSION = "1.0.0"


@dataclass
class CandidateResult:
    candidates: dict
    report: dict
    review: str


def show_hash(document: dict) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def rules_from(config: dict) -> RuleConfig:
    w = config["window"]
    return RuleConfig(w["min_duration_s"], w["max_duration_s"], w["tolerance_s"], max_segments=1, single_episode=True)


def find_candidates(show_doc: dict, config: dict, gold: Optional[dict] = None) -> CandidateResult:
    index = ShowIndex.from_show_json(show_doc)
    vocab, rules, tol = Vocabulary(config["vocabulary"]), rules_from(config), config["window"]["tolerance_s"]
    w = config["window"]

    episode_rows, skipped_episodes, all_scored, selected = [], [], [], []
    windows_by_episode: dict[str, list] = {}
    cut_totals, skip_totals = Counter(), Counter()
    violations, windows_failing = Counter(), 0

    for episode in index.episodes.values():
        if episode.untimed_blocks or episode.duration_s is None:
            skipped_episodes.append({"episode_id": episode.id, "reason": "has blocks without valid timestamps (see parse_report.json)"})
            continue

        cuts = find_cuts(episode, tol)
        rejected = cuts.rejection_counts(index.blocks)
        windows = enumerate_windows(episode.id, cuts.clean, w["min_duration_s"], w["max_duration_s"])
        windows_by_episode[episode.id] = windows

        for window in windows:  # independent hard-rule check on EVERY generated window
            found = validate_promo({"segments": promo_segments_from(window)}, index, rules)
            if found:
                windows_failing += 1
                violations.update(v.code for v in found)

        scorer = EpisodeScorer(episode, config, vocab)
        scored = [scorer.score(window) for window in windows]
        chosen = select_for_episode(scored, config["selection"])
        all_scored += scored
        selected += [(rank, s) for rank, s in enumerate(chosen.selected, start=1)]

        cut_totals.update({"boundaries": len(cuts.clean) + len(cuts.rejected), "clean": len(cuts.clean), **rejected})
        skip_totals.update(chosen.skipped)
        episode_rows.append({
            "episode_id": episode.id, "duration_s": episode.duration_s,
            "cut_points": {"boundaries": len(cuts.clean) + len(cuts.rejected), "clean": len(cuts.clean), **rejected},
            "valid_windows": len(windows),
            "selected": len(chosen.selected),
            "skipped": dict(sorted(chosen.skipped.items())),
            "top_score": chosen.selected[0].score if chosen.selected else None,
            "selected_ending_in_ending_zone": sum(s.ends_in_ending_zone for s in chosen.selected),
        })

    # show-wide ranking (score, then episode order, then time)
    episode_order = {eid: i for i, eid in enumerate(index.episodes)}
    selected.sort(key=lambda rs: (-rs[1].score, episode_order[rs[1].window.episode_id], rs[1].window.start.t, rs[1].window.end.t))
    records = []
    for rank, (episode_rank, s) in enumerate(selected, start=1):
        record = candidate_record(s, index, config, episode_rank)
        record["rank"] = rank
        records.append(record)

    # validate the final records exactly as written (segments + block and scene references)
    selected_failing = [r["id"] for r in records if validate_promo(r, index, rules)]

    meta = {"config_version": config["config_version"]}
    candidates_doc = {
        "schema_version": CANDIDATES_SCHEMA_VERSION,
        "config_version": config["config_version"],
        "config_sha256": config_hash(config),
        "show": {"title": index.title, "slug": index.slug, "show_schema_version": index.schema_version,
                 "show_sha256": show_hash(show_doc)},
        "candidates": records,
    }

    scored_selected = [s for _, s in selected]
    per_episode_counts = Counter(row["selected"] for row in episode_rows)
    report = {
        "schema_version": CANDIDATES_SCHEMA_VERSION,
        "config_version": config["config_version"],
        "config_sha256": config_hash(config),
        "counts": {
            "episodes_in_show": len(index.episodes),
            "episodes_processed": len(episode_rows),
            "episodes_skipped": skipped_episodes,
            "valid_windows": len(all_scored),
            "selected": len(records),
            "episodes_by_selected_count": {str(k): v for k, v in sorted(per_episode_counts.items())},
        },
        "cut_points": dict(sorted(cut_totals.items())),
        "selection_skips": dict(sorted(skip_totals.items())),
        "scores": {"all_windows": distribution([s.score for s in all_scored]),
                   "selected": distribution([s.score for s in scored_selected])},
        "feature_means": {"all_windows": feature_means(all_scored), "selected": feature_means(scored_selected)},
        "episode_endings": {
            "ending_zone_s": config["selection"]["ending_zone_s"],
            "cap_per_episode": config["selection"]["episode_ending_cap"],
            "windows_ending_in_zone": sum(s.ends_in_ending_zone for s in all_scored),
            "selected_ending_in_zone": sum(s.ends_in_ending_zone for s in scored_selected),
            "episodes_whose_top_candidate_is_the_ending": sum(
                1 for r in records if r["episode_rank"] == 1 and "ends_at_episode_end" in r["flags"]),
        },
        "scene_crossing": {
            "windows_crossing": sum(1 for s in all_scored if s.scene_crossings),
            "selected_crossing": sum(1 for s in scored_selected if s.scene_crossings),
        },
        "flags_selected": dict(sorted(Counter(f for r in records for f in r["flags"]).items())),
        "validation": {
            "windows_checked": len(all_scored), "windows_failing": windows_failing,
            "violations_by_code": dict(sorted(violations.items())),
            "selected_checked": len(records), "selected_failing": selected_failing,
        },
        "gold": evaluate_gold(gold, records, windows_by_episode, config["selection"]["per_episode"]),
        "episodes": episode_rows,
    }
    return CandidateResult(candidates_doc, report, review_markdown(records, index, meta))


def promo_segments_from(window) -> list[dict]:
    return [{"episode_id": window.episode_id, "start_s": window.start.t, "end_s": window.end.t,
             "start_block_id": window.start.block_id, "end_block_id": window.end.block_id}]


def dumps(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write_outputs(result: CandidateResult, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {"candidates.json": dumps(result.candidates), "candidates_report.json": dumps(result.report),
             "candidates_review.md": result.review}
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    return [out / n for n in files]

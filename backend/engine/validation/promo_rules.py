"""Hard rules every promo must satisfy, whoever proposed it (rules now, an AI later).

A promo is a dict:
    {"segments": [{"episode_id", "start_s", "end_s", "start_block_id"?, "end_block_id"?}, ...],
     "block_ids": [...]?, "scene_ids": [...]?}

validate_promo() returns a list of Violations; an empty list means the promo is valid.
This module deliberately re-implements the clean-cut check instead of importing the
candidate generator's version, so the two act as an independent cross-check.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from engine.screenplay.show_index import IndexedEpisode, ShowIndex

UNCUTTABLE_KINDS = ("dialogue", "camera")   # cutting inside these splits a spoken line or a shot


@dataclass(frozen=True)
class RuleConfig:
    min_duration_s: float = 20.0
    max_duration_s: float = 60.0
    tolerance_s: float = 0.011        # timestamps have two decimals; ignore float noise below this
    max_segments: int = 1             # Stage 2 candidates are one continuous clip
    single_episode: bool = True


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    segment: Optional[int] = None


def blocks_split_at(episode: IndexedEpisode, t: float, tol: float) -> list[str]:
    """IDs of dialogue/camera blocks that a cut at time t would split."""
    return [
        b.id for b in episode.blocks
        if b.kind in UNCUTTABLE_KINDS and b.is_timed and b.start_s < t - tol and b.end_s > t + tol
    ]


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_boundary_block(index: ShowIndex, episode: IndexedEpisode, block_id, t, tol, which, i) -> list[Violation]:
    if block_id is None:
        return []
    block = index.blocks.get(block_id)
    if block is None:
        return [Violation("unknown_block", f"{which}_block_id {block_id!r} does not exist", i)]
    if block.episode_id != episode.id:
        return [Violation("block_episode_mismatch", f"{block_id} belongs to {block.episode_id}, not {episode.id}", i)]
    if not any(edge is not None and abs(edge - t) <= tol for edge in (block.start_s, block.end_s)):
        return [Violation("boundary_mismatch", f"{which} time {t} is not a boundary of {block_id}", i)]
    return []


def _validate_segment(seg: dict, i: int, index: ShowIndex, rules: RuleConfig) -> tuple[list[Violation], Optional[float]]:
    tol = rules.tolerance_s
    episode = index.episodes.get(seg.get("episode_id"))
    if episode is None:
        return [Violation("unknown_episode", f"Episode {seg.get('episode_id')!r} does not exist", i)], None

    start, end = seg.get("start_s"), seg.get("end_s")
    if not (_is_number(start) and _is_number(end)):
        return [Violation("invalid_timestamp", f"start_s/end_s must be finite numbers, got {start!r}/{end!r}", i)], None
    if end - start <= tol:
        return [Violation("non_positive_segment", f"Segment ends at or before it starts ({start} -> {end})", i)], None

    violations = []
    if start < -tol or episode.duration_s is None or end > episode.duration_s + tol:
        violations.append(Violation("outside_episode", f"{start}-{end} is outside {episode.id} (0-{episode.duration_s})", i))
    for t, which in ((start, "start"), (end, "end")):
        split = blocks_split_at(episode, t, tol)
        if split:
            violations.append(Violation("unclean_cut", f"{which} cut at {t} splits {', '.join(split)}", i))
    violations += _check_boundary_block(index, episode, seg.get("start_block_id"), start, tol, "start", i)
    violations += _check_boundary_block(index, episode, seg.get("end_block_id"), end, tol, "end", i)
    return violations, round(end - start, 3)


def _overlaps(start, end, a, b, tol) -> bool:
    return start is not None and end is not None and start < b - tol and end > a + tol


def _check_references(promo: dict, index: ShowIndex, rules: RuleConfig) -> list[Violation]:
    tol = rules.tolerance_s
    spans = [(s.get("episode_id"), s.get("start_s"), s.get("end_s")) for s in promo["segments"]]
    violations = []
    for kind, ids, lookup in (("block", promo.get("block_ids") or [], index.blocks), ("scene", promo.get("scene_ids") or [], index.scenes)):
        for ref in ids:
            item = lookup.get(ref)
            if item is None:
                violations.append(Violation(f"unknown_{kind}", f"{kind} {ref!r} does not exist"))
            elif not any(item.episode_id == ep and _is_number(a) and _is_number(b) and _overlaps(item.start_s, item.end_s, a, b, tol)
                         for ep, a, b in spans):
                violations.append(Violation(f"{kind}_outside_promo", f"{ref} is not inside any segment of this promo"))
    return violations


def validate_promo(promo: dict, index: ShowIndex, rules: RuleConfig = RuleConfig()) -> list[Violation]:
    segments = promo.get("segments") or []
    if not segments:
        return [Violation("no_segments", "Promo has no segments")]

    violations: list[Violation] = []
    if len(segments) > rules.max_segments:
        violations.append(Violation("too_many_segments", f"{len(segments)} segments; at most {rules.max_segments} allowed"))
    episodes = {s.get("episode_id") for s in segments}
    if rules.single_episode and len(episodes) > 1:
        violations.append(Violation("cross_episode", f"Segments span episodes {sorted(map(str, episodes))}"))

    total = 0.0
    durations_known = True
    for i, segment in enumerate(segments):
        found, duration = _validate_segment(segment, i, index, rules)
        violations += found
        if duration is None:
            durations_known = False
        else:
            total += duration

    total = round(total, 3)
    if durations_known and not (rules.min_duration_s - 1e-9 <= total <= rules.max_duration_s + 1e-9):
        violations.append(Violation("duration_out_of_range", f"Total {total}s is outside {rules.min_duration_s}-{rules.max_duration_s}s"))
    violations += _check_references(promo, index, rules)
    return violations

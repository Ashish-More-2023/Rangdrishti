"""Step 5: choose up to N diverse candidates per episode (greedy, highest score first).

A window is skipped when:
  below_min_score  its score is under selection.min_score (six is a target, not a quota)
  overlap          it shares more than max_overlap of its time with an already chosen clip
  ending_cap       it ends in the episode's ending zone and the cap is already used
Overlap = shared seconds / the shorter clip's length, so a clip nested inside a
chosen one always counts as overlapping.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .scoring import ScoredWindow


@dataclass
class EpisodeSelection:
    selected: list[ScoredWindow] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)   # reason -> count


def overlap_fraction(a: ScoredWindow, b: ScoredWindow) -> float:
    shared = min(a.window.end.t, b.window.end.t) - max(a.window.start.t, b.window.start.t)
    if shared <= 0:
        return 0.0
    return shared / min(a.window.duration_s, b.window.duration_s)


def rank_key(s: ScoredWindow):
    # Highest score first; ties broken by earlier start, then shorter clip. Fully deterministic.
    return (-s.score, s.window.start.t, s.window.end.t)


def select_for_episode(scored: list[ScoredWindow], selection_cfg: dict) -> EpisodeSelection:
    result = EpisodeSelection()
    endings_used = 0
    for candidate in sorted(scored, key=rank_key):
        if len(result.selected) >= selection_cfg["per_episode"]:
            result.skipped["quota_filled"] += 1
        elif candidate.score < selection_cfg["min_score"]:
            result.skipped["below_min_score"] += 1
        elif any(overlap_fraction(candidate, chosen) > selection_cfg["max_overlap"] for chosen in result.selected):
            result.skipped["overlap"] += 1
        elif candidate.ends_in_ending_zone and endings_used >= selection_cfg["episode_ending_cap"]:
            result.skipped["ending_cap"] += 1
        else:
            result.selected.append(candidate)
            endings_used += candidate.ends_in_ending_zone
    return result

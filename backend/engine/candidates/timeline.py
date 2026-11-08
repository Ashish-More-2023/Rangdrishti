"""Step 1: where can a clip start or end?

Every block boundary (each block's start and end) is a possible cut. A cut is
CLEAN only if no dialogue block and no camera block runs across it, so a clip
never starts or ends mid-sentence or mid-shot. Action and sound blocks may be
trimmed; that is reported as a flag, not forbidden.

Times are kept exactly as parsed (two-decimal screenplay timestamps). Rounding to
3 decimals only merges float noise, never changes a value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.screenplay.show_index import IndexedBlock, IndexedEpisode

UNCUTTABLE_KINDS = ("dialogue", "camera")


@dataclass(frozen=True)
class CutPoint:
    t: float
    block_id: str          # a block that has a boundary exactly here (first in timeline order)
    edge: str              # "start" or "end" of that block
    raw: str               # the screenplay's own timestamp text for this boundary, e.g. "00:11.30"


@dataclass
class CutAnalysis:
    episode_id: str
    clean: list[CutPoint] = field(default_factory=list)
    rejected: list[tuple[CutPoint, tuple[str, ...]]] = field(default_factory=list)  # (cut, ids of blocks it splits)

    def rejection_counts(self, blocks_by_id: dict[str, IndexedBlock]) -> dict[str, int]:
        counts = {"splits_dialogue": 0, "splits_camera": 0, "splits_both": 0}
        for _, ids in self.rejected:
            kinds = {blocks_by_id[i].kind for i in ids}
            key = "splits_both" if kinds == {"dialogue", "camera"} else f"splits_{kinds.pop()}"
            counts[key] += 1
        return counts


def boundary_points(episode: IndexedEpisode) -> list[CutPoint]:
    """One CutPoint per distinct boundary time, credited to the first block (in timeline order) that has it."""
    seen: dict[float, CutPoint] = {}
    for block in episode.blocks:
        if not block.is_timed:
            continue
        for t, edge, raw in ((block.start_s, "start", block.start_raw), (block.end_s, "end", block.end_raw)):
            key = round(t, 3)
            if key not in seen:
                seen[key] = CutPoint(key, block.id, edge, raw or "")
    return [seen[t] for t in sorted(seen)]


def splitting_blocks(episode: IndexedEpisode, t: float, tol: float) -> tuple[str, ...]:
    return tuple(
        b.id for b in episode.blocks
        if b.kind in UNCUTTABLE_KINDS and b.is_timed and b.start_s < t - tol and b.end_s > t + tol
    )


def find_cuts(episode: IndexedEpisode, tol: float) -> CutAnalysis:
    analysis = CutAnalysis(episode.id)
    for point in boundary_points(episode):
        split = splitting_blocks(episode, point.t, tol)
        if split:
            analysis.rejected.append((point, split))
        else:
            analysis.clean.append(point)
    return analysis

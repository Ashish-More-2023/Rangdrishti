"""Step 2: list every continuous window between two clean cuts that lasts 20-60 s.

Windows never leave their episode: cuts come from one episode's timeline only,
because timestamps restart at 00:00 in every episode.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from engine.screenplay.show_index import IndexedBlock, IndexedEpisode

from .timeline import CutPoint


@dataclass(frozen=True)
class Window:
    episode_id: str
    start: CutPoint
    end: CutPoint

    @property
    def duration_s(self) -> float:
        return round(self.end.t - self.start.t, 3)

    @property
    def id(self) -> str:
        # Built from exact times (centiseconds), so the same window always has the same ID.
        return f"{self.episode_id}-W{round(self.start.t * 100):05d}-{round(self.end.t * 100):05d}"


def enumerate_windows(episode_id: str, cuts: list[CutPoint], min_s: float, max_s: float) -> list[Window]:
    """All (start, end) pairs of clean cuts with min_s <= duration <= max_s, both ends inclusive."""
    times = [c.t for c in cuts]
    windows = []
    for i, start in enumerate(cuts):
        # bisect narrows the search to ends roughly in range; the exact check is on the rounded duration
        lo = bisect.bisect_left(times, start.t + min_s - 0.001, lo=i + 1)
        hi = bisect.bisect_right(times, start.t + max_s + 0.001, lo=lo)
        for end in cuts[lo:hi]:
            duration = round(end.t - start.t, 3)
            if min_s <= duration <= max_s:
                windows.append(Window(episode_id, start, end))
    return windows


def blocks_in_window(episode: IndexedEpisode, window: Window, tol: float) -> list[IndexedBlock]:
    """Blocks that overlap the window by more than the tolerance, in timeline order."""
    a, b = window.start.t, window.end.t
    return [x for x in episode.blocks if x.is_timed and x.start_s < b - tol and x.end_s > a + tol]

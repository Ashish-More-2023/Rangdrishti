"""Step 4: combine the six features into one transparent score.

score = sum(weight_i * feature_i) - scene_crossing_penalty, clamped to [0, 1].
Every term is kept in the output, so any score can be explained line by line.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from engine.screenplay.show_index import IndexedEpisode

from .features import FEATURES, FeatureResult, Vocabulary, WindowContext
from .windows import Window, blocks_in_window


@dataclass(frozen=True)
class ScoredWindow:
    window: Window
    features: dict[str, FeatureResult]
    scene_crossings: int
    penalty: float
    score: float
    flags: tuple[str, ...]
    block_ids: tuple[str, ...]
    scene_ids: tuple[str, ...]
    trimmed_block_ids: tuple[str, ...]   # action/sound blocks cut by the window edges
    ends_in_ending_zone: bool


class EpisodeScorer:
    """Scores every window of one episode. Precomputes line lookups once per episode."""

    def __init__(self, episode: IndexedEpisode, config: dict, vocab: Vocabulary):
        self.episode, self.config, self.vocab = episode, config, vocab
        self.tol = config["window"]["tolerance_s"]
        self.lines = [b for b in episode.blocks if b.kind == "dialogue" and b.is_timed]
        self.line_starts = [b.start_s for b in self.lines]
        self.lines_by_end = sorted(self.lines, key=lambda b: (b.end_s, b.start_s, b.id))
        self.line_ends = [b.end_s for b in self.lines_by_end]

    def context(self, window: Window) -> WindowContext:
        a, b = window.start.t, window.end.t
        i = bisect.bisect_right(self.line_ends, a + self.tol)          # lines ending at or before the start
        j = bisect.bisect_left(self.line_starts, b - self.tol)         # first line starting at or after the end
        scenes = tuple(s for s in self.episode.scenes
                       if s.start_s is not None and s.end_s is not None and s.start_s < b - self.tol and s.end_s > a + self.tol)
        return WindowContext(
            episode=self.episode, window=window, blocks=tuple(blocks_in_window(self.episode, window, self.tol)),
            scenes=scenes, prev_line=self.lines_by_end[i - 1] if i else None,
            next_line=self.lines[j] if j < len(self.lines) else None, tol=self.tol,
        )

    def score(self, window: Window) -> ScoredWindow:
        cfg, ctx = self.config, self.context(window)
        features = {name: fn(ctx, cfg, self.vocab) for name, fn in FEATURES.items()}

        a, b = window.start.t, window.end.t
        crossings = sum(1 for s in ctx.scenes if s.start_s is not None and a + self.tol < s.start_s < b - self.tol)
        sc = cfg["scene_crossing"]
        penalty = round(min(sc["max_penalty"], sc["penalty_per_crossing"] * crossings), 4)
        weighted = sum(cfg["weights"][name] * f.value for name, f in features.items())
        score = round(max(0.0, min(1.0, weighted - penalty)), 4)

        trimmed = tuple(x.id for x in ctx.blocks if x.start_s < a - self.tol or x.end_s > b + self.tol)
        ending = self.episode.duration_s is not None and self.episode.duration_s - b <= cfg["selection"]["ending_zone_s"] + self.tol
        flags = []
        if crossings:
            flags.append("crosses_scene_boundary")
        if ending:
            flags.append("ends_at_episode_end")
        if a <= self.tol:
            flags.append("starts_at_episode_start")
        if trimmed:
            flags.append("trims_action_or_sound")
        if not ctx.lines:
            flags.append("no_dialogue")
        return ScoredWindow(window, features, crossings, penalty, score, tuple(flags),
                            tuple(x.id for x in ctx.blocks), tuple(s.id for s in ctx.scenes), trimmed, ending)

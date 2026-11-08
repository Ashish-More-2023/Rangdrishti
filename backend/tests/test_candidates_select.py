import unittest

from engine.candidates.scoring import ScoredWindow
from engine.candidates.select import overlap_fraction, select_for_episode
from engine.candidates.timeline import CutPoint
from engine.candidates.windows import Window

SEL = {"per_episode": 6, "max_overlap": 0.5, "min_score": 0.3, "episode_ending_cap": 1, "ending_zone_s": 3.0}


def sw(start, end, score, ending=False):
    w = Window("E001", CutPoint(start, "x", "start", ""), CutPoint(end, "x", "end", ""))
    return ScoredWindow(w, {}, 0, 0.0, score, (), (), (), (), ending)


def spans(selection):
    return [(s.window.start.t, s.window.end.t) for s in selection.selected]


class OverlapTests(unittest.TestCase):
    def test_overlap_is_measured_against_the_shorter_clip(self):
        self.assertEqual(overlap_fraction(sw(0, 60, 1), sw(10, 30, 1)), 1.0)     # nested
        self.assertEqual(overlap_fraction(sw(0, 30, 1), sw(30, 60, 1)), 0.0)     # touching
        self.assertEqual(overlap_fraction(sw(0, 30, 1), sw(15, 45, 1)), 0.5)


class SelectionTests(unittest.TestCase):
    def test_highest_first_and_overlap_over_half_is_skipped(self):
        result = select_for_episode([sw(0, 30, 0.9), sw(10, 40, 0.8), sw(15, 45, 0.7), sw(50, 80, 0.6)], SEL)
        self.assertEqual(spans(result), [(0, 30), (15, 45), (50, 80)])          # exactly 50% is allowed
        self.assertEqual(result.skipped["overlap"], 1)

    def test_six_is_a_target_not_a_quota(self):
        result = select_for_episode([sw(0, 30, 0.9), sw(40, 70, 0.25)], SEL)
        self.assertEqual(spans(result), [(0, 30)])
        self.assertEqual(result.skipped["below_min_score"], 1)

    def test_never_more_than_per_episode(self):
        many = [sw(i * 30, i * 30 + 25, 0.9 - i / 100) for i in range(10)]
        result = select_for_episode(many, SEL)
        self.assertEqual(len(result.selected), 6)
        self.assertEqual(result.skipped["quota_filled"], 4)

    def test_episode_ending_cap(self):
        windows = [sw(0, 30, 0.9, ending=True), sw(40, 70, 0.8, ending=True), sw(80, 110, 0.7)]
        self.assertEqual(spans(select_for_episode(windows, SEL)), [(0, 30), (80, 110)])
        self.assertEqual(spans(select_for_episode(windows, {**SEL, "episode_ending_cap": 0})), [(80, 110)])
        self.assertEqual(len(select_for_episode(windows, {**SEL, "episode_ending_cap": 2}).selected), 3)

    def test_ties_are_broken_deterministically(self):
        a = select_for_episode([sw(40, 70, 0.8), sw(0, 30, 0.8)], {**SEL, "per_episode": 1})
        b = select_for_episode([sw(0, 30, 0.8), sw(40, 70, 0.8)], {**SEL, "per_episode": 1})
        self.assertEqual(spans(a), spans(b))
        self.assertEqual(spans(a), [(0, 30)])

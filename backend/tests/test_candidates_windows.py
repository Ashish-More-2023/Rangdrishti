import unittest

from engine.candidates.timeline import CutPoint, find_cuts
from engine.candidates.windows import Window, blocks_in_window, enumerate_windows
from engine.screenplay.show_index import ShowIndex

from .candidate_helpers import show, standard_episode


def cut(t):
    return CutPoint(t, "E001-S01-B001", "start", "")


class WindowTests(unittest.TestCase):
    def test_both_ends_inclusive_and_nothing_outside_range(self):
        cuts = [cut(t) for t in (0.0, 19.99, 20.0, 60.0, 60.01)]
        got = {(w.start.t, w.end.t) for w in enumerate_windows("E001", cuts, 20.0, 60.0)}
        self.assertIn((0.0, 20.0), got)
        self.assertIn((0.0, 60.0), got)
        self.assertNotIn((0.0, 19.99), got)
        self.assertNotIn((0.0, 60.01), got)
        self.assertTrue(all(20.0 <= round(e - s, 3) <= 60.0 for s, e in got))

    def test_matches_brute_force_on_real_cut_structure(self):
        ep = ShowIndex.from_show_json(show(standard_episode())).episodes["E001"]
        clean = find_cuts(ep, 0.011).clean
        fast = {(w.start.t, w.end.t) for w in enumerate_windows("E001", clean, 20.0, 60.0)}
        brute = {(a.t, b.t) for i, a in enumerate(clean) for b in clean[i + 1:] if 20.0 <= round(b.t - a.t, 3) <= 60.0}
        self.assertEqual(fast, brute)
        self.assertGreater(len(fast), 0)

    def test_window_id_is_built_from_exact_times(self):
        self.assertEqual(Window("E007", cut(11.3), cut(45.8)).id, "E007-W01130-04580")

    def test_blocks_touching_an_edge_are_not_inside(self):
        ep = ShowIndex.from_show_json(show(standard_episode())).episodes["E001"]
        inside = blocks_in_window(ep, Window("E001", cut(20.0), cut(45.0)), 0.011)
        times = [(b.start_s, b.end_s) for b in inside]
        self.assertNotIn((15.0, 20.0), times)    # shot ending exactly at the start
        self.assertNotIn((45.0, 50.0), times)    # shot starting exactly at the end
        self.assertIn((13.0, 22.0), times)       # trimmed action block is inside

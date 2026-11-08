"""Clean-cut detection: never inside a spoken line or a camera shot; action/sound may be trimmed."""
import unittest

from engine.candidates.timeline import boundary_points, find_cuts
from engine.screenplay.show_index import ShowIndex

from .candidate_helpers import blk, episode, line, show, shots, standard_episode

TOL = 0.011


def index_of(*eps):
    return ShowIndex.from_show_json(show(*eps))


class CutTests(unittest.TestCase):
    def setUp(self):
        self.index = index_of(standard_episode())
        self.ep = self.index.episodes["E001"]
        self.cuts = find_cuts(self.ep, TOL)
        self.clean = {c.t for c in self.cuts.clean}
        self.rejected = {c.t: ids for c, ids in self.cuts.rejected}

    def test_shot_boundaries_between_lines_are_clean(self):
        for t in (0.0, 5.0, 10.0, 20.0, 90.0):
            self.assertIn(t, self.clean)

    def test_cut_inside_a_spoken_line_is_rejected(self):
        self.assertIn(15.0, self.rejected)                     # line 12.0-17.0 crosses the shot boundary
        kinds = {self.index.blocks[i].kind for i in self.rejected[15.0]}
        self.assertEqual(kinds, {"dialogue"})

    def test_cut_inside_a_camera_shot_is_rejected(self):
        self.assertIn(0.3, self.rejected)                      # line starts inside shot 0-5
        self.assertEqual({self.index.blocks[i].kind for i in self.rejected[0.3]}, {"camera"})

    def test_action_and_sound_blocks_never_block_a_cut(self):
        # action 13.0-22.0 spans the clean 20.0 cut
        self.assertIn(20.0, self.clean)

    def test_line_ending_exactly_on_a_boundary_is_clean(self):
        ep = index_of(episode(1, [(0.0, 30.0, shots(0, 30) + [line(7.0, 10.0, '"Go."')])])).episodes["E001"]
        self.assertIn(10.0, {c.t for c in find_cuts(ep, TOL).clean})

    def test_float_noise_inside_tolerance_does_not_reject(self):
        ep = index_of(episode(1, [(0.0, 30.0, shots(0, 30) + [line(7.0, 10.005, '"Go."')])])).episodes["E001"]
        self.assertIn(10.0, {c.t for c in find_cuts(ep, TOL).clean})

    def test_gap_without_camera_blocks_allows_cuts_at_any_boundary(self):
        blocks = shots(0, 20) + [blk("action", 20.0, 27.0, "Rain."), blk("action", 24.0, 30.0, "Thunder.")]
        ep = index_of(episode(1, [(0.0, 30.0, blocks)])).episodes["E001"]
        self.assertTrue({24.0, 27.0} <= {c.t for c in find_cuts(ep, TOL).clean})

    def test_boundary_points_are_unique_sorted_and_keep_raw_text(self):
        points = boundary_points(self.ep)
        times = [p.t for p in points]
        self.assertEqual(times, sorted(set(times)))
        five = next(p for p in points if p.t == 5.0)
        self.assertEqual((five.raw, five.edge), ("00:05.00", "end"))
        self.assertEqual(self.index.blocks[five.block_id].kind, "camera")

    def test_rejection_counts_by_kind(self):
        counts = self.cuts.rejection_counts(self.index.blocks)
        self.assertEqual(sum(counts.values()), len(self.cuts.rejected))
        self.assertGreater(counts["splits_dialogue"], 0)
        self.assertGreater(counts["splits_camera"], 0)

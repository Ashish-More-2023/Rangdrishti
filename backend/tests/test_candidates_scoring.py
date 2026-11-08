import unittest

from engine.candidates.features import Vocabulary
from engine.candidates.scoring import EpisodeScorer
from engine.candidates.timeline import find_cuts
from engine.candidates.windows import enumerate_windows
from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig, validate_promo

from .candidate_helpers import blk, config, episode, line, show, shots, standard_episode

CFG = config()


def scored(ep_doc):
    index = ShowIndex.from_show_json(show(ep_doc))
    ep = index.episodes[ep_doc["id"]]
    scorer = EpisodeScorer(ep, CFG, Vocabulary(CFG["vocabulary"]))
    return index, [scorer.score(w) for w in enumerate_windows(ep.id, find_cuts(ep, 0.011).clean, 20.0, 60.0)]


class ScoringTests(unittest.TestCase):
    def test_score_is_the_weighted_sum_minus_penalty(self):
        _, windows = scored(standard_episode())
        for s in windows:
            expected = sum(CFG["weights"][n] * f.value for n, f in s.features.items()) - s.penalty
            self.assertAlmostEqual(s.score, round(max(0.0, min(1.0, expected)), 4), places=4)
            self.assertTrue(0.0 <= s.score <= 1.0)

    def test_scene_crossing_is_penalised_and_flagged_not_rejected(self):
        ep = episode(1, [(0.0, 40.0, shots(0, 40) + [line(1.0, 3.0, '"Stop!"')]),
                         (40.0, 90.0, shots(40, 90) + [line(41.0, 43.0, '"No."')])])
        index, windows = scored(ep)
        crossing = [s for s in windows if s.scene_crossings]
        self.assertTrue(crossing)
        for s in crossing:
            self.assertIn("crosses_scene_boundary", s.flags)
            self.assertEqual(s.penalty, min(CFG["scene_crossing"]["max_penalty"], CFG["scene_crossing"]["penalty_per_crossing"] * s.scene_crossings))
            seg = {"episode_id": "E001", "start_s": s.window.start.t, "end_s": s.window.end.t}
            self.assertEqual(validate_promo({"segments": [seg]}, index, RuleConfig()), [])

    def test_flags(self):
        _, windows = scored(standard_episode())
        by_span = {(s.window.start.t, s.window.end.t): s for s in windows}
        self.assertIn("ends_at_episode_end", by_span[(60.0, 90.0)].flags)
        self.assertTrue(by_span[(60.0, 90.0)].ends_in_ending_zone)
        self.assertIn("starts_at_episode_start", by_span[(0.0, 30.0)].flags)
        self.assertIn("trims_action_or_sound", by_span[(20.0, 45.0)].flags)    # action 13-22 is cut at 20
        silent = episode(1, [(0.0, 60.0, shots(0, 60) + [blk("sound", 5.0, 6.0, "Wind.")])])
        self.assertTrue(all("no_dialogue" in s.flags for s in scored(silent)[1]))

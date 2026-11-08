"""Each of the six features, alone. Values follow directly from the config numbers."""
import types
import unittest

from engine.candidates.features import Vocabulary, cliffhanger, dialogue_density, duration_fit, hook, intensity, standalone
from engine.candidates.scoring import EpisodeScorer
from engine.candidates.timeline import CutPoint
from engine.candidates.windows import Window
from engine.screenplay.show_index import ShowIndex

from .candidate_helpers import blk, config, episode, line, show, shots, standard_episode

CFG = config()
VOCAB = Vocabulary(CFG["vocabulary"])


def ctx(ep_doc, start, end):
    ep = ShowIndex.from_show_json(show(ep_doc)).episodes[ep_doc["id"]]
    return EpisodeScorer(ep, CFG, VOCAB).context(Window(ep.id, CutPoint(start, "x", "start", ""), CutPoint(end, "x", "end", "")))


class HookTests(unittest.TestCase):
    def test_structural_hook_adds_up(self):
        f = hook(ctx(standard_episode(), 30.0, 60.0), CFG, VOCAB)
        h = CFG["hook"]
        self.assertAlmostEqual(f.value, h["speech_onset"] + h["intense_delivery"] + h["emphatic_punctuation"])
        self.assertEqual(f.keyword_bonus, 0.0)
        self.assertTrue(any("speaks 1.0s in" in r for r in f.reasons))

    def test_voice_over_counts_half(self):
        ep = episode(1, [(0.0, 60.0, shots(0, 60) + [line(0.5, 3.0, '"I remember."', voice="V.O.")])])
        self.assertAlmostEqual(hook(ctx(ep, 0.0, 30.0), CFG, VOCAB).value, CFG["hook"]["speech_onset"] * CFG["hook"]["voice_over_factor"])

    def test_no_speech_scores_zero_and_says_why(self):
        f = hook(ctx(standard_episode(), 35.0, 60.0), CFG, VOCAB)
        self.assertEqual(f.value, 0.0)
        self.assertIn("no speech in the first 3s", f.reasons)

    def test_fast_cutting(self):
        ep = episode(1, [(0.0, 60.0, shots(0, 3, every=1.0) + shots(3, 60))])
        self.assertAlmostEqual(hook(ctx(ep, 0.0, 30.0), CFG, VOCAB).value, CFG["hook"]["fast_cutting"])

    def test_keywords_are_capped_and_never_beat_structure(self):
        words = "She slaps him, grabs the knife, shatters the glass, screams and collapses."
        ep = episode(1, [(0.0, 60.0, shots(0, 60, text="Extreme close-up, crash zoom.") + [blk("action", 0.0, 2.0, words)])])
        keyword_only = hook(ctx(ep, 0.0, 30.0), CFG, VOCAB)
        self.assertEqual(keyword_only.keyword_bonus, CFG["keyword_bonus_max"])
        structural_only = hook(ctx(standard_episode(), 30.0, 60.0), CFG, VOCAB)
        self.assertGreater(structural_only.value, keyword_only.value)


class CliffhangerTests(unittest.TestCase):
    def test_question_intense_line_and_cut_before_reply(self):
        f = cliffhanger(ctx(standard_episode(), 30.0, 55.0), CFG, VOCAB)
        c = CFG["cliffhanger"]
        self.assertAlmostEqual(f.value, c["ends_on_question"] + c["intense_last_line"] + c["cuts_before_reply"])
        self.assertTrue(any("before BEN answers" in r for r in f.reasons))

    def test_episode_ending(self):
        f = cliffhanger(ctx(standard_episode(), 60.0, 90.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, CFG["cliffhanger"]["episode_end"])
        self.assertIn("ends at the episode's own ending", f.reasons)

    def test_scene_ending_that_is_not_the_episode_ending(self):
        ep = episode(1, [(0.0, 30.0, shots(0, 30)), (30.0, 60.0, shots(30, 60))])
        f = cliffhanger(ctx(ep, 0.0, 30.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, CFG["cliffhanger"]["scene_end"])

    def test_nothing_unresolved_is_explained(self):
        ep = episode(1, [(0.0, 90.0, shots(0, 90))])
        f = cliffhanger(ctx(ep, 0.0, 30.0), CFG, VOCAB)
        self.assertEqual(f.value, 0.0)
        self.assertTrue(f.reasons)


class DensityTests(unittest.TestCase):
    def density(self, *spans):
        ep = episode(1, [(0.0, 60.0, shots(0, 60, every=30.0) + [line(s, e, '"..."') for s, e in spans])])
        return dialogue_density(ctx(ep, 0.0, 30.0), CFG, VOCAB).value

    def test_bands(self):
        d = CFG["dialogue_density"]
        self.assertEqual(self.density((1.0, 4.0)), 0.0)                                   # 10% speech
        self.assertAlmostEqual(self.density((1.0, 10.0)), (0.3 - d["zero_below"]) / (d["ideal_min"] - d["zero_below"]), places=3)
        self.assertEqual(self.density((1.0, 19.0)), 1.0)                                  # 60%
        self.assertAlmostEqual(self.density((0.0, 30.0)), d["value_at_full"])             # 100%

    def test_overlapping_lines_are_not_double_counted(self):
        self.assertEqual(self.density((1.0, 19.0), (5.0, 15.0)), self.density((1.0, 19.0)))


class IntensityTests(unittest.TestCase):
    def test_structural_events_per_minute(self):
        f = intensity(ctx(standard_episode(), 30.0, 60.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, 2 / 0.5 / CFG["intensity"]["saturation_events_per_min"])   # 2 intense lines in 30 s

    def test_keyword_part_is_capped(self):
        many = [blk("action", t, t + 1.0, "He slams the door and collapses.") for t in range(0, 30, 2)]
        ep = episode(1, [(0.0, 60.0, shots(0, 60) + many)])
        f = intensity(ctx(ep, 0.0, 30.0), CFG, VOCAB)
        self.assertLessEqual(f.keyword_bonus, CFG["keyword_bonus_max"])
        self.assertAlmostEqual(f.value, f.keyword_bonus)    # no structural events at all


class StandaloneTests(unittest.TestCase):
    def test_clean_opening_at_scene_start(self):
        self.assertEqual(standalone(ctx(standard_episode(), 0.0, 30.0), CFG, VOCAB).value, 1.0)

    def test_dangling_opener(self):
        f = standalone(ctx(standard_episode(), 20.0, 45.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, 1.0 - CFG["standalone"]["dangling_opener"])

    def test_joining_a_conversation(self):
        f = standalone(ctx(standard_episode(), 55.0, 80.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, 1.0 - CFG["standalone"]["mid_conversation"])

    def test_too_many_speakers_and_voice_over(self):
        lines = [line(1.0 + 4 * i, 3.0 + 4 * i, '"Yes."', speaker=n) for i, n in enumerate("ABCDE")]
        ep = episode(1, [(0.0, 60.0, shots(0, 60, every=30.0) + lines)])
        f = standalone(ctx(ep, 0.0, 30.0), CFG, VOCAB)
        self.assertAlmostEqual(f.value, 1.0 - 2 * CFG["standalone"]["per_extra_speaker"] + CFG["standalone"]["scene_start_bonus"])
        vo = episode(1, [(0.0, 60.0, shots(0, 60, every=30.0) + [line(1.0, 20.0, '"Long ago..."', voice="V.O.")])])
        self.assertAlmostEqual(standalone(ctx(vo, 0.0, 30.0), CFG, VOCAB).value,
                               1.0 - CFG["standalone"]["voice_over_heavy"] + CFG["standalone"]["scene_start_bonus"])


class DurationFitTests(unittest.TestCase):
    def test_shape(self):
        def fit(d):
            window = Window("E001", CutPoint(0.0, "x", "start", ""), CutPoint(d, "x", "end", ""))
            return duration_fit(types.SimpleNamespace(window=window), CFG, VOCAB).value
        self.assertEqual([fit(20.0), fit(25.0), fit(30.0), fit(45.0), fit(52.5), fit(60.0)], [0.5, 0.75, 1.0, 1.0, 0.75, 0.5])

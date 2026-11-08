"""Hard rules for any promo. Each violation code is exercised once."""
import unittest

from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig, validate_promo

from .candidate_helpers import show, standard_episode

INDEX = ShowIndex.from_show_json(show(standard_episode(1), standard_episode(2)))


def seg(start, end, episode="E001", **extra):
    return {"episode_id": episode, "start_s": start, "end_s": end, **extra}


def codes(promo, rules=RuleConfig()):
    return {v.code for v in validate_promo(promo, INDEX, rules)}


def block_at(episode_id, kind, start):
    return next(b.id for b in INDEX.episodes[episode_id].blocks if b.kind == kind and b.start_s == start)


class PromoRuleTests(unittest.TestCase):
    def test_valid_promo_passes_including_exact_limits(self):
        self.assertEqual(codes({"segments": [seg(30.0, 55.0)]}), set())
        self.assertEqual(codes({"segments": [seg(30.0, 50.0)]}), set())     # exactly 20 s
        self.assertEqual(codes({"segments": [seg(20.0, 80.0)]}), set())     # exactly 60 s

    def test_duration_limits(self):
        self.assertIn("duration_out_of_range", codes({"segments": [seg(30.0, 45.0)]}))
        self.assertIn("duration_out_of_range", codes({"segments": [seg(20.0, 85.0)]}))

    def test_unclean_cuts_name_the_split_block(self):
        found = validate_promo({"segments": [seg(15.0, 45.0)]}, INDEX)        # 15 s is inside a spoken line
        self.assertEqual([v.code for v in found], ["unclean_cut"])
        self.assertIn(block_at("E001", "dialogue", 12.0), found[0].message)
        self.assertIn("unclean_cut", codes({"segments": [seg(2.0, 30.0)]}))   # 2 s is inside a camera shot

    def test_timestamp_problems(self):
        self.assertIn("invalid_timestamp", codes({"segments": [seg("00:30.00", 55.0)]}))
        self.assertIn("invalid_timestamp", codes({"segments": [seg(float("nan"), 55.0)]}))
        self.assertIn("non_positive_segment", codes({"segments": [seg(55.0, 30.0)]}))
        self.assertIn("outside_episode", codes({"segments": [seg(70.0, 95.0)]}))

    def test_episode_isolation(self):
        self.assertIn("unknown_episode", codes({"segments": [seg(30.0, 55.0, "E099")]}))
        two = {"segments": [seg(30.0, 40.0), seg(30.0, 40.0, "E002")]}
        self.assertTrue({"cross_episode", "too_many_segments"} <= codes(two))
        self.assertEqual(codes(two, RuleConfig(max_segments=2, single_episode=False)), set())   # Stage 4 will allow this
        self.assertIn("no_segments", codes({"segments": []}))

    def test_source_block_references(self):
        start_shot = block_at("E001", "camera", 30.0)
        self.assertEqual(codes({"segments": [seg(30.0, 55.0, start_block_id=start_shot)]}), set())
        self.assertIn("unknown_block", codes({"segments": [seg(30.0, 55.0, start_block_id="E001-S01-B999")]}))
        self.assertIn("block_episode_mismatch", codes({"segments": [seg(30.0, 55.0, start_block_id=block_at("E002", "camera", 30.0))]}))
        self.assertIn("boundary_mismatch", codes({"segments": [seg(30.0, 55.0, end_block_id=start_shot)]}))

    def test_block_and_scene_lists(self):
        inside, outside = block_at("E001", "camera", 30.0), block_at("E001", "camera", 70.0)
        self.assertEqual(codes({"segments": [seg(30.0, 55.0)], "block_ids": [inside], "scene_ids": ["E001-S01"]}), set())
        self.assertIn("block_outside_promo", codes({"segments": [seg(30.0, 55.0)], "block_ids": [outside]}))
        self.assertIn("block_outside_promo", codes({"segments": [seg(30.0, 55.0)], "block_ids": [block_at("E002", "camera", 30.0)]}))
        self.assertIn("unknown_block", codes({"segments": [seg(30.0, 55.0)], "block_ids": ["nope"]}))
        self.assertIn("unknown_scene", codes({"segments": [seg(30.0, 55.0)], "scene_ids": ["E001-S09"]}))
        self.assertIn("scene_outside_promo", codes({"segments": [seg(30.0, 55.0)], "scene_ids": ["E002-S01"]}))

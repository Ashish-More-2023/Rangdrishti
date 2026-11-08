"""Validation reports problems and never changes data."""
import copy
import unittest
from dataclasses import asdict

from engine.screenplay.parser import parse_episode
from engine.screenplay.validate import validate_show

from .screenplay_helpers import BROKEN_PACK, MINIMAL, codes_at, fixture_source, source


def episode_from(text, name="synthetic-ep-003.txt"):
    return parse_episode(source(text, name)).episode


class ValidateTests(unittest.TestCase):
    def test_broken_fixture_semantic_issues(self):
        episode = parse_episode(fixture_source(BROKEN_PACK / "synthetic-ep-007.txt")).episode
        found = codes_at(validate_show([episode]))
        self.assertIn(("scene_missing_boundary", 8), found)
        self.assertIn(("block_negative_duration", 21), found)

    def test_validation_does_not_modify_data(self):
        episode = parse_episode(fixture_source(BROKEN_PACK / "synthetic-ep-007.txt")).episode
        before = copy.deepcopy(asdict(episode))
        validate_show([episode])
        self.assertEqual(asdict(episode), before)

    def test_block_after_scene_end_is_a_warning(self):
        ep = episode_from(MINIMAL.replace("End: (00:05.00)", "End: (00:10.30)"))
        issues = [i for i in validate_show([ep]) if i.code == "block_after_scene_end"]
        self.assertEqual([i.severity for i in issues], ["warning"])

    def test_scene_gap_and_overlap(self):
        second = "\nSCENE 02\nScene heading: INT. HALL – DAY\nScene start: {start}\nScene end: 00:30.00\n\nActions and dialogue:\n"
        gap = episode_from(MINIMAL + second.format(start="00:12.00"))
        overlap = episode_from(MINIMAL + second.format(start="00:08.00"))
        self.assertIn("scene_gap", {i.code for i in validate_show([gap])})
        self.assertIn("scene_overlap", {i.code for i in validate_show([overlap])})

    def test_duplicate_and_missing_episode_numbers(self):
        eps = [episode_from(MINIMAL, "synthetic-ep-003.txt"), episode_from(MINIMAL, "synthetic-ep-003b.txt"),
               episode_from(MINIMAL.replace("Episode 3", "Episode 6"), "synthetic-ep-006.txt")]
        codes = {i.code for i in validate_show(eps)}
        self.assertIn("duplicate_episode_number", codes)
        self.assertIn("duplicate_id", codes)
        self.assertIn("episode_numbering_gap", codes)

    def test_header_and_filename_number_mismatch(self):
        ep = episode_from(MINIMAL, "synthetic-ep-004.txt")
        self.assertIn("episode_number_mismatch", {i.code for i in validate_show([ep])})

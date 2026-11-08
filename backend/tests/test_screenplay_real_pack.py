"""Runs only where the confidential Kuku pack is present; skipped everywhere else.

Looks at RANGDRISHTI_REAL_PACK (folder or .zip) or the first pack inside data/input.
It checks invariants, not hard-coded counts, so it also works on a new pack.
"""
import os
import unittest
from collections import Counter
from pathlib import Path

from engine.screenplay import parse_show

DATA_INPUT = Path(__file__).resolve().parents[2] / "data" / "input"


def find_real_pack():
    if os.getenv("RANGDRISHTI_REAL_PACK"):
        path = Path(os.environ["RANGDRISHTI_REAL_PACK"])
        return path if path.exists() else None
    if not DATA_INPUT.is_dir():
        return None
    for candidate in sorted(DATA_INPUT.iterdir()):
        if candidate.suffix.lower() == ".zip" or (candidate.is_dir() and any(candidate.rglob("*.txt"))):
            return candidate
    return None


REAL_PACK = find_real_pack()


@unittest.skipUnless(REAL_PACK, "Confidential input pack not available (set RANGDRISHTI_REAL_PACK or use data/input)")
class RealPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = parse_show(REAL_PACK)
        cls.report = cls.result.report
        cls.blocks = [b for e in cls.result.show.episodes for s in e.scenes for b in s.blocks]
        counts = cls.report["counts"]
        print(f"\n[real pack] {counts['episodes']} episodes, {counts['scenes']} scenes, {counts['blocks']} blocks, "
              f"{cls.report['issues']['errors']} errors, {cls.report['lines']['unaccounted']} unaccounted lines")

    def test_no_errors(self):
        errors = [i for i in self.report["issues"]["items"] if i["severity"] == "error"]
        self.assertEqual(errors, [])

    def test_no_unaccounted_lines(self):
        self.assertEqual(self.report["lines"]["unaccounted_lines"], [])

    def test_one_episode_per_file(self):
        self.assertEqual(self.report["counts"]["episodes"], self.report["input"]["files"])

    def test_ids_are_unique(self):
        duplicates = [i for i, c in Counter(b.id for b in self.blocks).items() if c > 1]
        self.assertEqual(duplicates, [])

    def test_every_block_is_timed_and_has_text(self):
        self.assertTrue(all(b.start_s is not None and b.end_s is not None and b.text for b in self.blocks))

    def test_no_speaker_name_contains_parentheses(self):
        self.assertFalse([b.speaker for b in self.blocks if b.speaker and "(" in b.speaker])

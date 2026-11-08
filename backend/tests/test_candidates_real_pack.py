"""Stage 2 on the confidential pack. Skipped unless the pack is available locally.

Checks invariants, not hard-coded counts, so it also works on a new show."""
import unittest
from collections import Counter

from engine.candidates import find_candidates, load_config
from engine.candidates.pipeline import dumps
from engine.screenplay import parse_show

from .test_screenplay_real_pack import REAL_PACK


@unittest.skipUnless(REAL_PACK, "Confidential input pack not available (set RANGDRISHTI_REAL_PACK or use data/input)")
class RealPackCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.show = parse_show(REAL_PACK).show_json
        cls.result = find_candidates(cls.show, load_config())
        cls.report = cls.result.report
        cls.records = cls.result.candidates["candidates"]
        c = cls.report["counts"]
        print(f"\n[real pack] {c['episodes_processed']} episodes, {c['valid_windows']} valid windows, "
              f"{c['selected']} candidates, {cls.report['validation']['windows_failing']} windows failing rules")

    def test_every_episode_is_processed(self):
        self.assertEqual(self.report["counts"]["episodes_skipped"], [])

    def test_no_window_or_candidate_breaks_a_hard_rule(self):
        v = self.report["validation"]
        self.assertEqual((v["windows_failing"], v["selected_failing"]), (0, []))

    def test_per_episode_limit_and_duration(self):
        self.assertTrue(all(n <= 6 for n in Counter(r["episode_id"] for r in self.records).values()))
        self.assertTrue(all(20.0 <= r["duration_s"] <= 60.0 for r in self.records))

    def test_ending_cap_respected(self):
        endings = Counter(r["episode_id"] for r in self.records if "ends_at_episode_end" in r["flags"])
        self.assertTrue(all(n <= load_config()["selection"]["episode_ending_cap"] for n in endings.values()))

    def test_deterministic(self):
        again = find_candidates(self.show, load_config())
        self.assertEqual(dumps(again.candidates), dumps(self.result.candidates))

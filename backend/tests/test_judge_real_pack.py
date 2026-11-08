"""Stage 3 mechanics on the confidential pack with the offline mock. Skipped without the pack."""
import tempfile
import unittest
from pathlib import Path

from engine.ai import MockProvider
from engine.candidates import find_candidates, load_config
from engine.judge import judge_show, load_judge_config
from engine.screenplay import parse_show

from .test_screenplay_real_pack import REAL_PACK


@unittest.skipUnless(REAL_PACK, "Confidential input pack not available")
class RealPackJudgeTests(unittest.TestCase):
    def test_every_candidate_is_judged_and_valid(self):
        show = parse_show(REAL_PACK).show_json
        cands = find_candidates(show, load_config()).candidates
        with tempfile.TemporaryDirectory() as tmp:
            r = judge_show(show, cands, MockProvider(), load_judge_config(), Path(tmp))
        self.assertEqual(r.report["counts"]["judged"], len(cands["candidates"]))
        self.assertEqual((r.report["validation"]["promos_failing"], r.failed_episodes), ([], []))

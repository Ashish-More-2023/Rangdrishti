"""The annotation kit must be neutral (no candidates or scores) and must never overwrite human picks."""
import inspect
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.evaluation import worksheet
from engine.evaluation.gold import evaluate_gold, parse_picks
from engine.evaluation.worksheet import blank_gold, build_worksheet, write_kit

from .candidate_helpers import show, standard_episode

SHOW = show(standard_episode(1), standard_episode(2))
TEMPLATE = Path(__file__).resolve().parents[2] / "docs" / "gold_promos.template.json"


class WorksheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_worksheet_lists_every_spoken_line_and_blank_pick_slots(self):
        text = build_worksheet(SHOW)
        self.assertIn('"Where were you last night?"', text)
        self.assertIn("| 00:31.00 | 00:34.00 | ANA (Shouting) |", text)
        self.assertEqual(len(re.findall(r"^\| G\d\d \|", text, re.M)), 15)

    def test_worksheet_is_built_without_candidates_or_scores(self):
        source = inspect.getsource(worksheet)
        self.assertNotIn("engine.candidates", source)
        self.assertNotIn("score", build_worksheet(SHOW).lower().replace("contains no candidates or scores", ""))
        self.assertIsNone(re.search(r"E\d{3}-W\d{5}-\d{5}", build_worksheet(SHOW)))

    def test_blank_gold_has_the_agreed_schema_and_no_picks(self):
        gold = blank_gold(SHOW)
        self.assertEqual(gold["promos"], [])
        self.assertTrue({"labeler", "method", "promos"} <= gold.keys())
        self.assertEqual(set(gold["blank_pick"]), {"id", "segments", "hook", "cliffhanger", "why", "confidence"})
        self.assertEqual(set(gold["blank_pick"]["segments"][0]), {"episode_id", "start", "end"})
        self.assertEqual(parse_picks(gold), ([], []))
        self.assertEqual(evaluate_gold(gold, [], {}, 6)["status"], "empty")
        self.assertEqual(set(json.loads(TEMPLATE.read_text(encoding="utf-8"))), set(gold))

    def test_existing_gold_file_is_never_overwritten(self):
        first = write_kit(SHOW, self.tmp)
        self.assertEqual(first["gold_status"], "created blank file")
        (self.tmp / "gold_promos.json").write_text('{"promos": [{"id": "MINE"}]}', encoding="utf-8")
        second = write_kit(SHOW, self.tmp)
        self.assertIn("kept existing", second["gold_status"])
        self.assertIn("MINE", (self.tmp / "gold_promos.json").read_text(encoding="utf-8"))

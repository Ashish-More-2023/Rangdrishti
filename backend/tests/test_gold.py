"""Gold-set evaluation. The repo template must stay empty: only a person adds picks."""
import json
import unittest
from pathlib import Path

from engine.candidates import find_candidates, load_config
from engine.candidates.timeline import find_cuts
from engine.candidates.windows import enumerate_windows
from engine.evaluation.gold import evaluate_gold, parse_picks
from engine.screenplay.show_index import ShowIndex

from .candidate_helpers import show, standard_episode

TEMPLATE = Path(__file__).resolve().parents[2] / "docs" / "gold_promos.template.json"


def pick(pid, ep, start, end):
    return {"id": pid, "segments": [{"episode_id": ep, "start": start, "end": end}]}


class GoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.show = show(standard_episode(1))
        cls.result = find_candidates(cls.show, load_config())
        cls.records = cls.result.candidates["candidates"]
        ep = ShowIndex.from_show_json(cls.show).episodes["E001"]
        cls.windows = {"E001": enumerate_windows("E001", find_cuts(ep, 0.011).clean, 20.0, 60.0)}

    def test_repository_template_has_no_picks(self):
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(template["promos"], [])
        self.assertEqual(evaluate_gold(template, self.records, self.windows, 6)["status"], "empty")

    def test_missing_gold_is_reported_not_invented(self):
        self.assertEqual(evaluate_gold(None, self.records, self.windows, 6)["status"], "not_provided")

    def test_recall_and_baseline(self):
        top = self.records[0]["segments"][0]
        gold = {"promos": [pick("G01", "E001", top["start_raw"], top["end_raw"]),     # same span as a candidate
                           pick("G02", "E002", "00:10.00", "00:40.00")]}              # episode with no candidates
        out = evaluate_gold(gold, self.records, self.windows, 6)
        self.assertEqual((out["status"], out["picks"], out["recall"]), ("evaluated", 2, 0.5))
        self.assertEqual(out["details"][0]["covered_by"], self.records[0]["id"])
        self.assertEqual(out, evaluate_gold(gold, self.records, self.windows, 6))      # fixed seed: repeatable
        self.assertTrue(0.0 <= out["random_baseline_recall"] <= 1.0)

    def test_bad_picks_are_listed_not_guessed(self):
        picks, problems = parse_picks({"promos": [pick("G01", "E001", "00:40.00", "00:10.00"), {"id": "G02"}]})
        self.assertEqual((picks, [p["id"] for p in problems]), ([], ["G01", "G02"]))

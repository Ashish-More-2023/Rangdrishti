"""End-to-end Stage 2 on synthetic shows: validity, determinism, outputs, config and CLI."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.candidates import find_candidates, load_config, write_outputs
from engine.candidates.cli import run
from engine.candidates.config import ConfigError, check_config
from engine.candidates.pipeline import dumps
from engine.screenplay import parse_show

from .candidate_helpers import blk, config, episode, show, shots, standard_episode
from .screenplay_helpers import CLEAN_PACK

SHOW = show(standard_episode(1), standard_episode(2))


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = find_candidates(SHOW, load_config())
        cls.records = cls.result.candidates["candidates"]
        cls.report = cls.result.report

    def test_every_window_and_candidate_passes_hard_rules(self):
        v = self.report["validation"]
        self.assertGreater(v["windows_checked"], 0)
        self.assertEqual((v["windows_failing"], v["selected_failing"]), (0, []))

    def test_at_most_six_per_episode_and_all_within_limits(self):
        per_episode = {}
        for r in self.records:
            per_episode[r["episode_id"]] = per_episode.get(r["episode_id"], 0) + 1
            self.assertTrue(20.0 <= r["duration_s"] <= 60.0)
            self.assertGreaterEqual(r["score"], load_config()["selection"]["min_score"])
        self.assertTrue(all(n <= 6 for n in per_episode.values()))

    def test_ranks_ids_and_exact_timestamps(self):
        self.assertEqual([r["rank"] for r in self.records], list(range(1, len(self.records) + 1)))
        self.assertEqual(len({r["id"] for r in self.records}), len(self.records))
        scores = [r["score"] for r in self.records]
        self.assertEqual(scores, sorted(scores, reverse=True))
        seg = self.records[0]["segments"][0]
        self.assertRegex(seg["start_raw"], r"^\d\d:\d\d\.\d\d$")

    def test_output_is_byte_for_byte_deterministic(self):
        again = find_candidates(SHOW, load_config())
        self.assertEqual(dumps(again.candidates), dumps(self.result.candidates))
        self.assertEqual(dumps(again.report), dumps(self.result.report))
        self.assertEqual(again.review, self.result.review)

    def test_provenance_is_recorded(self):
        cfg = load_config()
        self.assertEqual(self.result.candidates["config_version"], cfg["config_version"])
        self.assertEqual(len(self.result.candidates["config_sha256"]), 64)
        self.assertEqual(len(self.result.candidates["show"]["show_sha256"]), 64)

    def test_selection_accounting_adds_up(self):
        skips = sum(self.report["selection_skips"].values())
        self.assertEqual(skips + self.report["counts"]["selected"], self.report["counts"]["valid_windows"])

    def test_gold_not_provided_by_default(self):
        self.assertEqual(self.report["gold"]["status"], "not_provided")

    def test_episode_with_untimed_blocks_is_skipped_and_reported(self):
        bad = episode(3, [(0.0, 60.0, shots(0, 60) + [blk("action", None, None, "Broken timing.")])])
        result = find_candidates(show(standard_episode(1), bad), load_config())
        self.assertEqual([e["episode_id"] for e in result.report["counts"]["episodes_skipped"]], ["E003"])
        self.assertFalse([r for r in result.candidates["candidates"] if r["episode_id"] == "E003"])

    def test_works_on_parser_output(self):
        parsed = parse_show(CLEAN_PACK).show_json
        result = find_candidates(parsed, load_config())
        self.assertEqual(result.report["validation"]["windows_failing"], 0)
        self.assertGreater(result.report["counts"]["valid_windows"], 0)

    def test_unsupported_schema_is_refused(self):
        with self.assertRaises(ValueError):
            find_candidates({**SHOW, "schema_version": "2.0.0"}, load_config())


class ConfigTests(unittest.TestCase):
    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ConfigError):
            check_config(config(**{"weights.hook": 0.9}))

    def test_keywords_can_only_ever_be_a_small_bonus(self):
        with self.assertRaises(ConfigError):
            check_config(config(keyword_bonus_max=0.5))

    def test_changing_the_cap_changes_selection(self):
        none = find_candidates(SHOW, config(**{"selection.episode_ending_cap": 0}))
        self.assertFalse([r for r in none.candidates["candidates"] if "ends_at_episode_end" in r["flags"]])


class OutputAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_write_outputs(self):
        written = write_outputs(find_candidates(SHOW, load_config()), self.tmp)
        self.assertEqual(sorted(p.name for p in written), ["candidates.json", "candidates_report.json", "candidates_review.md"])
        self.assertIn("score breakdown", (self.tmp / "candidates_review.md").read_text(encoding="utf-8"))

    def test_cli_exit_codes(self):
        (self.tmp / "show.json").write_text(json.dumps(SHOW), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run([str(self.tmp)], data_dir=self.tmp), 0)                 # folder containing show.json
            self.assertEqual(run([str(self.tmp / "missing.json")], data_dir=self.tmp), 2)
        self.assertTrue((self.tmp / "candidates.json").exists())

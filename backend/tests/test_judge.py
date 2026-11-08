"""Stage 3 on synthetic data: parsing, trims, scoring, caching, fallback, determinism."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.ai import MockProvider, ProviderError, ProviderResponse
from engine.candidates import find_candidates, load_config
from engine.judge import judge_show, load_judge_config, write_outputs
from engine.judge.combine import try_trim
from engine.judge.parse import Judgment, parse_judgments
from engine.judge.prompts import build_messages
from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig

from .candidate_helpers import show, standard_episode

SHOW = show(standard_episode(1), standard_episode(2))
CANDS = find_candidates(SHOW, load_config()).candidates
INDEX = ShowIndex.from_show_json(SHOW)
CFG = load_judge_config()


def judgment(cid, **kw):
    base = dict(candidate_id=cid, hook_score=8, cliffhanger_score=7, standalone_score=6, verdict="post",
                hook="h", cliffhanger="c", why="w", suggested_start_block_id=None, suggested_end_block_id=None)
    base.update(kw)
    return Judgment(**base)


class FixedProvider:
    """Returns a scripted answer; records how often it was called."""
    name, model = "fixed", "fixed-1"

    def __init__(self, text):
        self.text, self.calls = text, 0

    def complete(self, request):
        self.calls += 1
        return ProviderResponse(self.text, self.model)


class FailingProvider(FixedProvider):
    def complete(self, request):
        self.calls += 1
        raise ProviderError("HTTP 429 after 5 attempt(s)")


class ParseTests(unittest.TestCase):
    IDS = ["A", "B", "C"]

    def item(self, cid, **kw):
        d = {"candidate_id": cid, "hook_score": 7, "cliffhanger_score": 6, "standalone_score": 5, "verdict": "Post",
             "hook": "h", "cliffhanger": "c", "why": "w"}
        d.update(kw)
        return d

    def test_fenced_json_and_verdict_case(self):
        text = "```json\n" + json.dumps({"judgments": [self.item("A")]}) + "\n```"
        r = parse_judgments(text, self.IDS)
        self.assertEqual(r.judgments["A"].verdict, "post")
        self.assertEqual({i["code"] for i in r.issues}, {"not_judged"})

    def test_bad_items_are_reported_not_repaired(self):
        items = [self.item("A", hook_score=11), self.item("B", verdict="great"), self.item("Z"), self.item("C"), self.item("C")]
        r = parse_judgments(json.dumps({"judgments": items}), self.IDS)
        self.assertEqual(list(r.judgments), ["C"])
        self.assertEqual(sorted(i["code"] for i in r.issues), ["duplicate_judgment", "invalid_fields", "invalid_fields", "unknown_candidate"])

    def test_garbage_is_fatal(self):
        self.assertIsNotNone(parse_judgments("Sure! Here are my thoughts...", self.IDS).fatal)


class TrimTests(unittest.TestCase):
    def setUp(self):
        self.c = CANDS["candidates"][0]
        self.ep = INDEX.episodes[self.c["episode_id"]]

    def block_at(self, kind, t, edge="start_s"):
        return next(b.id for b in self.ep.blocks if b.kind == kind and getattr(b, edge) == t)

    def test_no_suggestion_keeps_original(self):
        seg, trim = try_trim(self.c, judgment(self.c["id"]), INDEX, RuleConfig(), 0.5)
        self.assertEqual((seg, trim["applied"]), (self.c["segments"][0], False))

    def test_invalid_or_foreign_suggestions_are_rejected(self):
        for bad in ("E999-S01-B001", self.block_at("dialogue", 12.0)):     # unknown / would cut mid-shot
            seg, trim = try_trim(self.c, judgment(self.c["id"], suggested_start_block_id=bad), INDEX, RuleConfig(), 0.5)
            self.assertFalse(trim["applied"])
            self.assertEqual(seg, self.c["segments"][0])
            self.assertTrue(trim["reason"])

    def test_valid_trim_is_applied_and_original_kept_on_record(self):
        applied = []
        for c in CANDS["candidates"]:
            seg0 = c["segments"][0]
            ep = INDEX.episodes[c["episode_id"]]
            for shot in (b for b in ep.blocks if b.kind == "camera" and seg0["start_s"] < b.start_s < seg0["end_s"]):
                seg, trim = try_trim(c, judgment(c["id"], suggested_start_block_id=shot.id), INDEX, RuleConfig(), 0.5)
                if trim["applied"]:
                    applied.append((seg, trim, seg0, shot))
        self.assertTrue(applied, "expected at least one valid start trim on the synthetic show")
        seg, trim, seg0, shot = applied[0]
        self.assertEqual((seg["start_s"], seg["start_block_id"], trim["original"]), (shot.start_s, shot.id, seg0))
        self.assertGreaterEqual(seg["end_s"] - seg["start_s"], 20.0)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_mock_run_is_valid_complete_and_flagged_as_mock(self):
        r = judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp)
        self.assertEqual(r.report["counts"]["judged"], len(CANDS["candidates"]))
        self.assertEqual(r.report["validation"]["promos_failing"], [])
        self.assertIn("MOCK", r.report["mock_warning"])
        finals = [p["final_score"] for p in r.promos["promos"]]
        self.assertEqual(finals, sorted(finals, reverse=True))

    def test_final_score_arithmetic(self):
        p = judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp).promos["promos"][0]
        a = p["ai"]
        ai = (0.4 * a["hook_score"] + 0.4 * a["cliffhanger_score"] + 0.2 * a["standalone_score"]) / 10
        self.assertAlmostEqual(p["final_score"], round(0.3 * p["rule_score"] + 0.7 * round(ai, 4), 4), places=4)

    def test_cache_makes_reruns_free_and_identical(self):
        first_provider, second_provider = MockProvider(), MockProvider()
        a = judge_show(SHOW, CANDS, first_provider, CFG, self.tmp)
        b = judge_show(SHOW, CANDS, second_provider, CFG, self.tmp)
        self.assertEqual((first_provider.calls, second_provider.calls), (2, 0))
        self.assertEqual(json.dumps(a.promos, sort_keys=True), json.dumps(b.promos, sort_keys=True))

    def test_raw_output_saved_verbatim_and_separately(self):
        text = '{"judgments": []}  '
        judge_show(SHOW, CANDS, FixedProvider(text), CFG, self.tmp / "raw")
        files = list((self.tmp / "raw").glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertEqual(json.loads(files[0].read_text())["response_text"], text)

    def test_provider_failure_falls_back_to_rule_scores(self):
        r = judge_show(SHOW, CANDS, FailingProvider(""), CFG, self.tmp)
        self.assertEqual(sorted(r.failed_episodes), ["E001", "E002"])
        self.assertEqual(r.report["counts"]["judged"], 0)
        self.assertTrue(all(p["final_score"] is None and not p["judged"] for p in r.promos["promos"]))
        self.assertEqual(list(self.tmp.glob("*.json")), [])            # nothing cached for a failed call

    def test_unreadable_response_is_a_failure(self):
        r = judge_show(SHOW, CANDS, FixedProvider("I think they are all great!"), CFG, self.tmp)
        self.assertEqual(sorted(r.failed_episodes), ["E001", "E002"])

    def test_post_first_skips_skip_verdicts_and_limits_per_episode(self):
        r = judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp)
        first = r.promos["post_first"]
        self.assertLessEqual(len(first), CFG["post_first"]["count"])
        self.assertEqual(len({p["episode_id"] for p in first}), len(first))
        verdicts = {p["id"]: p["ai"]["verdict"] for p in r.promos["promos"]}
        self.assertNotIn("skip", {verdicts[p["id"]] for p in first})

    def test_episode_filter_and_call_limit(self):
        r = judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp, episodes={"E001"})
        self.assertEqual(r.report["calls"]["episode_status"]["E002"], "not_requested")
        r2 = judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp / "other", max_calls=1)
        self.assertEqual(len(r2.report["calls"]["skipped_by_call_limit"]), 1)

    def test_outputs_written(self):
        written = write_outputs(judge_show(SHOW, CANDS, MockProvider(), CFG, self.tmp), self.tmp / "out")
        self.assertEqual(sorted(p.name for p in written), ["judge_report.json", "promos.csv", "promos.json"])
        self.assertTrue((self.tmp / "out" / "promos.csv").read_text(encoding="utf-8-sig").startswith("rank,post_first_rank"))


class PromptTests(unittest.TestCase):
    def test_prompt_lists_every_block_and_candidate(self):
        ep = INDEX.episodes["E001"]
        cands = [c for c in CANDS["candidates"] if c["episode_id"] == "E001"]
        user = build_messages("Synthetic Show", ep, "A logline.", cands)[1]["content"]
        for b in ep.blocks:
            self.assertIn(b.id, user)
        for c in cands:
            self.assertIn(c["id"], user)

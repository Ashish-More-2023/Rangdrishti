import shutil
import tempfile
import unittest
from pathlib import Path

from engine.results import ResultNotFound, clip_detail, csv_path, list_shows, show_results

from .results_helpers import SLUG, build_processed


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.data)

    def test_lists_shows_and_flags_mock_runs(self):
        build_processed(self.data)
        (shown,) = list_shows(self.data)
        self.assertEqual((shown["slug"], shown["has_promos"], shown["is_mock"]), (SLUG, True, True))

    def test_results_are_ranked_with_post_first_ids(self):
        build_processed(self.data)
        r = show_results(self.data, SLUG)
        self.assertEqual([p["rank"] for p in r["promos"]], list(range(1, len(r["promos"]) + 1)))
        self.assertTrue(set(r["post_first"]) <= {p["id"] for p in r["promos"]})
        self.assertTrue(r["run"]["is_mock"])
        self.assertTrue(r["csv_available"])

    def test_clip_lists_the_screenplay_inside_the_promo(self):
        build_processed(self.data)
        promo = show_results(self.data, SLUG)["promos"][0]
        clip = clip_detail(self.data, SLUG, promo["id"])
        self.assertTrue(clip["lines"])
        self.assertTrue(all(promo["start_s"] - 10 < line["start_s"] < promo["end_s"] for line in clip["lines"]))

    def test_unjudged_show_explains_the_next_step(self):
        build_processed(self.data, judged=False)
        with self.assertRaises(ResultNotFound) as ctx:
            show_results(self.data, SLUG)
        self.assertEqual(ctx.exception.code, "not_judged")
        self.assertIn("judge_promos", ctx.exception.message)

    def test_paths_outside_processed_are_refused(self):
        build_processed(self.data)
        for slug in ("../etc", "UPPER", "a/b", ""):
            with self.assertRaises(ResultNotFound):
                show_results(self.data, slug)
        with self.assertRaises(ResultNotFound):
            clip_detail(self.data, SLUG, "../../secret")
        with self.assertRaises(ResultNotFound):
            csv_path(self.data, "missing-show")

    def test_no_processed_folder_means_no_shows(self):
        self.assertEqual(list_shows(self.data), [])

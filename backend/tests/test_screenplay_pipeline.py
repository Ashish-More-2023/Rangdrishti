"""End-to-end: ZIP and folder input, determinism, stable IDs and written outputs."""
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.screenplay import SCHEMA_VERSION, parse_show, write_outputs
from engine.screenplay.serialize import dumps

from .screenplay_helpers import BROKEN_PACK, CLEAN_PACK, MINIMAL, non_blank_lines


def all_blocks(show_json):
    return {b["id"]: b for e in show_json["episodes"] for s in e["scenes"] for b in s["blocks"]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_clean_pack_has_no_errors_or_unaccounted_lines(self):
        result = parse_show(CLEAN_PACK)
        report = result.report
        self.assertEqual(report["issues"]["errors"], 0)
        self.assertEqual(report["issues"]["warnings"], 0)
        self.assertEqual(report["lines"]["unaccounted"], 0)
        expected_lines = sum(non_blank_lines(p.read_text(encoding="utf-8")) for p in CLEAN_PACK.glob("*.txt"))
        self.assertEqual(report["lines"]["non_blank"], expected_lines)
        self.assertEqual((report["counts"]["episodes"], report["counts"]["scenes"], report["counts"]["blocks"]), (2, 3, 11))
        self.assertEqual(result.show.title, "The Lighthouse Heir")

    def test_zip_and_directory_inputs_give_the_same_episodes(self):
        archive = self.tmp / "pack.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in sorted(CLEAN_PACK.glob("*.txt")):
                zf.write(path, f"The Lighthouse Heir/{path.name}")
        from_dir, from_zip = parse_show(CLEAN_PACK), parse_show(archive)
        self.assertEqual(from_dir.show_json["episodes"], from_zip.show_json["episodes"])
        self.assertEqual(from_zip.show.title, "The Lighthouse Heir")
        self.assertEqual(from_zip.show_json["show"]["source_origin"], "zip")

    def test_output_is_byte_for_byte_deterministic(self):
        first, second = parse_show(CLEAN_PACK), parse_show(CLEAN_PACK)
        self.assertEqual(dumps(first.show_json), dumps(second.show_json))
        self.assertEqual(dumps(first.report), dumps(second.report))
        self.assertEqual(first.renderings, second.renderings)

    def test_ids_are_stable_when_another_episode_is_added(self):
        before = all_blocks(parse_show(CLEAN_PACK).show_json)
        pack = self.tmp / "The Lighthouse Heir"
        shutil.copytree(CLEAN_PACK, pack)
        (pack / "synthetic-ep-000.txt").write_text(MINIMAL.replace("Episode 3", "Episode 3"), encoding="utf-8")
        after = all_blocks(parse_show(pack).show_json)
        for block_id, block in before.items():
            self.assertEqual(after[block_id]["text"], block["text"])
        self.assertEqual(before["E001-S01-B003"]["text"], '"It\'s mine now.\nAll of it."')

    def test_speakers_are_normalised_and_voice_is_kept(self):
        blocks = all_blocks(parse_show(CLEAN_PACK).show_json)
        self.assertEqual(blocks["E001-S01-B003"]["speaker"], "MARA")          # LADY MARA, title rule
        self.assertEqual(blocks["E001-S02-B001"]["speaker"], "TOBIAS")        # SIR TOBIAS, title rule
        self.assertEqual(blocks["E001-S02-B001"]["voice"], "O.S.")
        self.assertEqual(blocks["E002-S01-B002"]["annotations"], ["Edmund"])

    def test_outputs_written_and_stale_renderings_removed(self):
        out = self.tmp / "out"
        (out / "episodes").mkdir(parents=True)
        (out / "episodes" / "E099.txt").write_text("stale")
        write_outputs(parse_show(CLEAN_PACK), out)
        self.assertEqual(sorted(p.name for p in (out / "episodes").iterdir()), ["E001.txt", "E002.txt"])
        show = json.loads((out / "show.json").read_text(encoding="utf-8"))
        report = json.loads((out / "parse_report.json").read_text(encoding="utf-8"))
        self.assertEqual(show["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        rendering = (out / "episodes" / "E001.txt").read_text(encoding="utf-8")
        self.assertIn('E001-S01-B005 00:09.00-00:12.00 MARA [V.O.] (Quiet, Certain): "I knew his voice', rendering)

    def test_broken_pack_reports_errors_and_unaccounted_lines(self):
        report = parse_show(BROKEN_PACK).report
        self.assertGreater(report["issues"]["errors"], 0)
        self.assertEqual(report["lines"]["unaccounted"], 3)
        self.assertEqual(len(report["lines"]["unaccounted_lines"]), 3)

    def test_alias_file_is_used_and_recorded(self):
        aliases = self.tmp / "speaker_aliases.json"
        aliases.write_text(json.dumps({"aliases": {"HARBOR MASTER": "EDMUND"}}))
        result = parse_show(CLEAN_PACK, aliases)
        self.assertEqual(all_blocks(result.show_json)["E002-S01-B002"]["speaker"], "EDMUND")
        self.assertIn({"raw": "HARBOR MASTER", "canonical": "EDMUND", "rule": "manual"}, result.report["speakers"]["merges"])

    def test_missing_input_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_show(self.tmp / "nope")

    def test_json_contains_no_absolute_paths(self):
        text = dumps(parse_show(CLEAN_PACK).show_json) + dumps(parse_show(CLEAN_PACK).report)
        self.assertNotIn(str(CLEAN_PACK.parent), text)

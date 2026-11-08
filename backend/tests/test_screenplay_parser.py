"""State machine tests: structure, line accounting, label handling and error reporting."""
import unittest

from engine.screenplay.parser import classify_label, parse_episode

from .screenplay_helpers import BROKEN_PACK, CLEAN_PACK, MINIMAL, codes_at, fixture_source, non_blank_lines, source


class CleanEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = fixture_source(CLEAN_PACK / "synthetic-ep-001.txt")
        cls.result = parse_episode(cls.src)
        cls.ep = cls.result.episode
        cls.blocks = [b for s in cls.ep.scenes for b in s.blocks]

    def test_structure(self):
        self.assertEqual(self.ep.number, 1)
        self.assertEqual([s.number for s in self.ep.scenes], [1, 2])
        self.assertEqual(len(self.blocks), 8)
        self.assertEqual([b.kind for b in self.blocks[:6]], ["camera", "action", "dialogue", "dialogue", "dialogue", "sound"])

    def test_every_non_blank_line_is_accounted_for(self):
        self.assertEqual(sum(self.result.line_categories.values()), non_blank_lines(self.src.text))
        self.assertEqual(self.result.line_categories["unaccounted"], 0)
        self.assertEqual(self.result.issues, [])

    def test_multiline_dialogue_kept_verbatim_with_line_numbers(self):
        mara = self.blocks[2]
        self.assertEqual(mara.text, '"It\'s mine now.\nAll of it."')
        self.assertEqual(mara.source.text_lines, [25, 26])

    def test_source_is_preserved(self):
        mara = self.blocks[2]
        self.assertEqual(mara.source.label, "LADY MARA (Breathless)")
        self.assertEqual(mara.source.speaker_raw, "LADY MARA")
        self.assertEqual((mara.source.label_line, mara.source.timing_line), (23, 24))
        self.assertEqual((mara.source.start_raw, mara.source.end_raw), ("00:04.00", "00:07.50"))
        self.assertEqual((mara.start_s, mara.end_s), (4.0, 7.5))

    def test_header_fields_and_continuation(self):
        self.assertIn("The logline continues on a second line.", self.ep.logline)
        self.assertEqual(self.ep.source.header["EPISODE NUMBER"], "Episode 1")

    def test_ids_follow_screenplay_numbering(self):
        self.assertEqual(self.blocks[0].id, "E001-S01-B001")
        self.assertEqual(self.ep.scenes[1].blocks[0].id, "E001-S02-B001")


class LabelTests(unittest.TestCase):
    def test_missing_delivery(self):
        parts = classify_label("TOBIAS")
        self.assertEqual((parts.kind, parts.speaker_raw, parts.delivery, parts.voice), ("dialogue", "TOBIAS", None, None))

    def test_label_variants(self):
        cases = {
            "CAMERA": ("camera", None, None, None, ()),
            "Sound FX": ("sound", None, None, None, ()),
            "HOUSEKEEPER (Cold, Commanding)": ("dialogue", "HOUSEKEEPER", "Cold, Commanding", None, ()),
            "MARA (V.O.) (Quiet, Certain)": ("dialogue", "MARA", "Quiet, Certain", "V.O.", ()),
            "SIR TOBIAS (O.S. / Continues)": ("dialogue", "SIR TOBIAS", None, "O.S.", ("continues",)),
            "MARA (Off-screen)": ("dialogue", "MARA", None, "O.S.", ()),
            "HARBOR MASTER (Edmund) (Gruff)": ("dialogue", "HARBOR MASTER", "Gruff", None, ("Edmund",)),
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                p = classify_label(label)
                self.assertEqual((p.kind, p.speaker_raw, p.delivery, p.voice, p.annotations), expected)
                self.assertEqual(p.leftover, "")


class CaseVariationTests(unittest.TestCase):
    def test_upper_case_scene_headers_parse_like_lower_case(self):
        upper = MINIMAL.replace("Scene heading:", "SCENE HEADING:").replace("Scene start:", "SCENE START:") \
                       .replace("Scene end:", "SCENE END:").replace("Actions and dialogue:", "ACTIONS AND DIALOGUE:")
        a, b = parse_episode(source(MINIMAL)), parse_episode(source(upper))
        sa, sb = a.episode.scenes[0], b.episode.scenes[0]
        self.assertEqual((sa.heading, sa.start_s, sa.end_s, len(sa.blocks)), (sb.heading, sb.start_s, sb.end_s, len(sb.blocks)))
        self.assertEqual(b.issues, [])
        self.assertEqual(sb.source.start_raw, "00:00.00")


class BrokenEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = fixture_source(BROKEN_PACK / "synthetic-ep-007.txt")
        cls.result = parse_episode(cls.src)
        cls.found = codes_at(cls.result.issues)
        cls.blocks = [b for s in cls.result.episode.scenes for b in s.blocks]

    def test_expected_parse_issues_at_expected_lines(self):
        expected = {
            ("unrecognized_line", 6), ("unrecognized_line", 12), ("invalid_timestamp", 15),
            ("block_missing_timing", 18), ("text_before_timing", 19), ("malformed_timing_line", 26),
            ("missing_section_marker", 33), ("unrecognized_line", 36),
        }
        self.assertTrue(expected <= self.found, expected - self.found)

    def test_unrecognized_lines_are_kept_not_dropped(self):
        texts = [u["text"] for u in self.result.unaccounted]
        self.assertEqual(texts, ["Stray line before any scene.", "Editor note: check this take.", "Start: (00:12.00) | End: (00:13.00)"])
        self.assertEqual(sum(self.result.line_categories.values()), non_blank_lines(self.src.text))

    def test_invalid_timestamp_is_not_repaired(self):
        camera = self.blocks[0]
        self.assertEqual(camera.source.start_raw, "00:0x.00")
        self.assertIsNone(camera.start_s)
        self.assertEqual(camera.end_s, 4.0)

    def test_block_without_timing_keeps_its_text(self):
        action = self.blocks[1]
        self.assertIsNone(action.source.timing_line)
        self.assertEqual(action.text, "Ivy drops the letter.")

    def test_scene_without_boundaries_has_no_invented_times(self):
        scene = self.result.episode.scenes[0]
        self.assertIsNone(scene.start_s)
        self.assertIsNone(scene.source.start_raw)


class EdgeCaseTests(unittest.TestCase):
    def test_missing_script_start_is_warned_but_parsed(self):
        result = parse_episode(source(MINIMAL.replace("--- SCRIPT START ---", "")))
        self.assertIn("missing_script_start", {i.code for i in result.issues})
        self.assertEqual(len(result.episode.scenes[0].blocks), 1)

    def test_file_without_script_is_an_error(self):
        result = parse_episode(source("EPISODE NUMBER: Episode 4\n"))
        self.assertIn("no_script_body", {i.code for i in result.issues})

    def test_unreadable_file_is_an_error(self):
        from engine.screenplay.sources import SourceFile
        result = parse_episode(SourceFile("synthetic-ep-009.txt", "", "x", None, "not valid UTF-8"))
        self.assertIn("unreadable_file", {i.code for i in result.issues})
        self.assertEqual(result.episode.number, 9)

    def test_episode_number_falls_back_to_filename_with_warning(self):
        result = parse_episode(source(MINIMAL.replace("EPISODE NUMBER: Episode 3\n", ""), "synthetic-ep-012.txt"))
        self.assertEqual(result.episode.number, 12)
        self.assertIn("episode_number_from_filename", {i.code for i in result.issues})

    def test_crlf_line_endings(self):
        result = parse_episode(source(MINIMAL.replace("\n", "\r\n")))
        self.assertEqual(result.issues, [])
        self.assertEqual(result.episode.scenes[0].blocks[0].text, "A wide shot.")

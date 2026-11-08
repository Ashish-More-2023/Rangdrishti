"""Speaker normalisation: title rule and manual aliases, tested independently."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from engine.screenplay.normalize import build_speaker_map, load_aliases, normalize_episodes, speaker_form
from engine.screenplay.parser import parse_episode

from .screenplay_helpers import MINIMAL, source


class TitleRuleTests(unittest.TestCase):
    def map(self, *names, manual=None):
        return build_speaker_map(Counter({n: 1 for n in names}), manual or {})

    def test_title_merges_when_bare_name_also_speaks(self):
        m = self.map("LADY MARA", "MARA")
        self.assertEqual((m["LADY MARA"].canonical, m["LADY MARA"].rule), ("MARA", "title"))
        self.assertEqual(m["MARA"].rule, "identity")

    def test_title_does_not_merge_when_bare_name_never_speaks(self):
        self.assertEqual(self.map("LORD WREN")["LORD WREN"].canonical, "LORD WREN")

    def test_title_alone_or_descriptions_are_never_merged(self):
        m = self.map("LORD", "THE CAPTAIN", "TOBIAS", "OLD FISHERMAN")
        self.assertTrue(all(v.rule == "identity" for v in m.values()))

    def test_spelling_clean_up_only(self):
        self.assertEqual(speaker_form("  lady   Mara: "), "LADY MARA")


class ManualAliasTests(unittest.TestCase):
    def test_manual_alias_applies_without_title_rule(self):
        m = build_speaker_map(Counter({"HARBOR MASTER": 3, "EDMUND": 1}), {"HARBOR MASTER": "EDMUND"})
        self.assertEqual((m["HARBOR MASTER"].canonical, m["HARBOR MASTER"].rule), ("EDMUND", "manual"))

    def test_manual_alias_overrides_title_rule(self):
        m = build_speaker_map(Counter({"LADY MARA": 1, "MARA": 1}), {"LADY MARA": "MARA THE ELDER"})
        self.assertEqual((m["LADY MARA"].canonical, m["LADY MARA"].rule), ("MARA THE ELDER", "manual"))

    def test_load_aliases_normalises_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "speaker_aliases.json"
            path.write_text(json.dumps({"schema_version": 1, "aliases": {"harbor  master": "Edmund"}}))
            aliases, issues = load_aliases(path)
        self.assertEqual((aliases, issues), ({"HARBOR MASTER": "EDMUND"}, []))

    def test_invalid_alias_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "speaker_aliases.json"
            path.write_text('{"aliases": ["not", "a", "dict"]}')
            aliases, issues = load_aliases(path)
            self.assertEqual(aliases, {})
            self.assertEqual(issues[0].code, "aliases_invalid")
            path.write_text("{broken json")
            self.assertEqual(load_aliases(path)[1][0].code, "aliases_unreadable")


class NormalizeEpisodesTests(unittest.TestCase):
    def test_raw_label_survives_normalisation_and_unused_alias_is_reported(self):
        text = MINIMAL + '\n**LADY ROSE (Soft):**\nStart: (00:05.00) | End: (00:06.00)\n"Hello."\n\n**ROSE:**\nStart: (00:06.00) | End: (00:07.00)\n"Hi."\n'
        episode = parse_episode(source(text)).episode
        mapping, issues = normalize_episodes([episode], {"NOBODY": "SOMEONE"})
        lady = episode.scenes[0].blocks[1]
        self.assertEqual((lady.speaker, lady.source.speaker_raw, lady.source.label), ("ROSE", "LADY ROSE", "LADY ROSE (Soft)"))
        self.assertIn("unused_alias", {i.code for i in issues})
        self.assertEqual(episode.duration_s, 10.0)

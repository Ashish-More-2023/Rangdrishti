"""Normalisation: canonical speaker names and derived values.

Speaker rule, in priority order:
  1. manual alias from speaker_aliases.json (a human decision always wins)
  2. title rule: "LADY MARA" -> "MARA", but only if "MARA" also speaks
     somewhere in the show. A title alone ("THE CAPTAIN") is never merged with a
     name ("TOBIAS"): that would need story knowledge, which is a human call.
  3. otherwise the name itself (upper-cased, spaces collapsed)
The raw label is always kept in block.source.speaker_raw.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import Episode, Issue

TITLES = frozenset({
    "LADY", "LORD", "SIR", "DAME", "DUKE", "DUCHESS", "PRINCE", "PRINCESS", "KING", "QUEEN",
    "COUNT", "COUNTESS", "EARL", "BARON", "BARONESS", "MR", "MRS", "MS", "MISS", "DR",
})
ALIASES_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SpeakerMapping:
    raw_form: str
    canonical: str
    rule: str  # "manual" | "title" | "identity"


def speaker_form(name: str) -> str:
    """Spelling-level clean-up only: case, spacing, trailing punctuation."""
    return " ".join(name.upper().split()).rstrip(".:,;").strip()


def load_aliases(path: Optional[Path]) -> tuple[dict[str, str], list[Issue]]:
    if path is None:
        return {}, []
    name = Path(path).name
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [Issue("error", "aliases_unreadable", f"Cannot read speaker aliases: {exc}", name)]
    aliases = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(aliases, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()):
        return {}, [Issue("error", "aliases_invalid", 'Expected {"aliases": {"RAW NAME": "CANONICAL NAME"}}', name)]
    return {speaker_form(k): speaker_form(v) for k, v in aliases.items()}, []


def build_speaker_map(observed: Counter, manual: dict[str, str]) -> dict[str, SpeakerMapping]:
    """observed: speaker_form -> number of dialogue blocks."""
    mapping: dict[str, SpeakerMapping] = {}
    for form in sorted(observed):
        if form in manual:
            mapping[form] = SpeakerMapping(form, manual[form], "manual")
            continue
        first, _, rest = form.partition(" ")
        if first in TITLES and rest and rest in observed:
            mapping[form] = SpeakerMapping(form, manual.get(rest, rest), "title")
        else:
            mapping[form] = SpeakerMapping(form, form, "identity")
    return mapping


def observed_speakers(episodes: list[Episode]) -> Counter:
    counts: Counter = Counter()
    for block in iter_blocks(episodes):
        if block.kind == "dialogue" and block.source.speaker_raw:
            counts[speaker_form(block.source.speaker_raw)] += 1
    return counts


def iter_blocks(episodes: list[Episode]):
    for episode in episodes:
        for scene in episode.scenes:
            yield from scene.blocks


def normalize_episodes(episodes: list[Episode], manual: dict[str, str]) -> tuple[dict[str, SpeakerMapping], list[Issue]]:
    observed = observed_speakers(episodes)
    mapping = build_speaker_map(observed, manual)
    for block in iter_blocks(episodes):
        if block.kind == "dialogue" and block.source.speaker_raw:
            block.speaker = mapping[speaker_form(block.source.speaker_raw)].canonical

    for episode in episodes:
        ends = [t for s in episode.scenes for t in [s.end_s, *(b.end_s for b in s.blocks)] if t is not None]
        episode.duration_s = max(ends) if ends else None

    issues = []
    noted = set()
    for block in iter_blocks(episodes):
        for note in block.annotations:
            pair = (block.speaker, note)
            if note != "continues" and pair not in noted:
                noted.add(pair)
                issues.append(Issue("info", "speaker_annotation",
                                    f"{block.speaker} is annotated {note!r}; add a manual alias if this is another speaker's name",
                                    "(show)", None))
    issues += [
        Issue("info", "unused_alias", f"Alias {raw!r} never appears in this pack", "speaker_aliases.json")
        for raw in sorted(manual) if raw not in observed
    ]
    return mapping, issues

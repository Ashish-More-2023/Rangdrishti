"""Turn the data model into show.json. Field order is fixed, so output is byte-for-byte deterministic."""
from __future__ import annotations

import json
from dataclasses import asdict

from .models import Episode
from .normalize import SpeakerMapping


def show_document(*, schema_version, parser_version, title, slug, origin, episodes: list[Episode],
                  speaker_map: dict[str, SpeakerMapping]) -> dict:
    speakers: dict[str, dict] = {}
    for mapping in speaker_map.values():
        entry = speakers.setdefault(mapping.canonical, {"raw_forms": [], "rules": []})
        entry["raw_forms"].append(mapping.raw_form)
        if mapping.rule not in entry["rules"]:
            entry["rules"].append(mapping.rule)
    return {
        "schema_version": schema_version,
        "parser_version": parser_version,
        "show": {"title": title, "slug": slug, "source_origin": origin},
        "speakers": dict(sorted(speakers.items())),
        "episodes": [asdict(e) for e in episodes],
    }


def dumps(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"

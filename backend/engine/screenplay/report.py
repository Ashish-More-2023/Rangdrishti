"""Build parse_report.json: counts, line accounting, issues and speaker merges."""
from __future__ import annotations

from collections import Counter

from .models import Episode, Issue
from .normalize import SpeakerMapping, iter_blocks
from .parser import FileParse
from .render import render_episode

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def issue_dict(issue: Issue) -> dict:
    return {"severity": issue.severity, "code": issue.code, "message": issue.message, "file": issue.file, "line": issue.line}


def build_report(*, schema_version, parser_version, pack, parses: list[FileParse], episodes: list[Episode],
                 issues: list[Issue], speaker_map: dict[str, SpeakerMapping], aliases_file) -> dict:
    blocks = list(iter_blocks(episodes))
    categories = sum((p.line_categories for p in parses), Counter())
    labels = sum((p.labels for p in parses), Counter())
    ordered = sorted(issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.file, i.line or 0, i.code))
    severities = Counter(i.severity for i in issues)

    return {
        "schema_version": schema_version,
        "parser_version": parser_version,
        "input": {"title": pack.title, "origin": pack.origin, "files": len(pack.files), "speaker_aliases": aliases_file},
        "counts": {
            "episodes": len(episodes),
            "scenes": sum(len(e.scenes) for e in episodes),
            "blocks": len(blocks),
            "blocks_by_kind": dict(sorted(Counter(b.kind for b in blocks).items())),
            "multiline_blocks": sum(1 for b in blocks if len(b.source.text_lines) > 1),
            "blocks_with_missing_or_invalid_time": sum(1 for b in blocks if b.start_s is None or b.end_s is None),
            "speakers_raw": len(speaker_map),
            "speakers_canonical": len({m.canonical for m in speaker_map.values()}),
            "total_runtime_s": round(sum(e.duration_s or 0 for e in episodes), 2),
        },
        "lines": {
            "non_blank": sum(categories.values()),
            "by_category": dict(sorted(categories.items())),
            "unaccounted": categories.get("unaccounted", 0),
            "unaccounted_lines": [u for p in parses for u in p.unaccounted],
        },
        "issues": {
            "errors": severities.get("error", 0),
            "warnings": severities.get("warning", 0),
            "info": severities.get("info", 0),
            "by_code": dict(sorted(Counter(i.code for i in issues).items())),
            "items": [issue_dict(i) for i in ordered],
        },
        "speakers": {
            "merges": [
                {"raw": m.raw_form, "canonical": m.canonical, "rule": m.rule}
                for m in speaker_map.values() if m.rule != "identity"
            ],
            "unmerged_count": sum(1 for m in speaker_map.values() if m.rule == "identity"),
        },
        "label_names": dict(sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))),
        "episodes": [
            {
                "id": e.id, "number": e.number, "file": e.source.file,
                "scenes": len(e.scenes), "blocks": sum(len(s.blocks) for s in e.scenes),
                "duration_s": e.duration_s,
                "est_tokens": len(render_episode(e)) // 4,  # rough: ~4 characters per token
            }
            for e in episodes
        ],
    }

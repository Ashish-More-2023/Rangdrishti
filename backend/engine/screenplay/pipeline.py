"""Wire the parser steps together: load -> parse -> normalise -> validate -> report."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import Episode, Issue, Show
from .normalize import load_aliases, normalize_episodes
from .parser import parse_episode
from .render import render_episode
from .report import build_report
from .serialize import dumps, show_document
from .sources import load_pack
from .validate import validate_show

PARSER_VERSION = "1.0.0"


@dataclass
class ParseResult:
    show: Show
    show_json: dict
    report: dict
    renderings: dict[str, str]   # episode id -> compact text

    @property
    def error_count(self) -> int:
        return self.report["issues"]["errors"]


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "show"


def _sort_key(episode: Episode):
    return (episode.number is None, episode.number or 0, episode.source.file)


def parse_show(path: str | Path, aliases_path: Optional[str | Path] = None) -> ParseResult:
    from . import SCHEMA_VERSION  # late import avoids a cycle with __init__

    pack = load_pack(path)
    manual, issues = load_aliases(Path(aliases_path) if aliases_path else None)
    if not pack.files:
        issues.append(Issue("error", "no_screenplay_files", "No .txt screenplay files found", str(Path(path).name)))

    parses = [parse_episode(source, ordinal) for ordinal, source in enumerate(pack.files, start=1)]
    episodes = sorted((p.episode for p in parses), key=_sort_key)
    issues += [issue for p in parses for issue in p.issues]

    speaker_map, normalize_issues = normalize_episodes(episodes, manual)
    issues += normalize_issues

    issues += validate_show(episodes)

    show = Show(title=pack.title, slug=slugify(pack.title), episodes=episodes)
    versions = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION}
    document = show_document(**versions, title=show.title, slug=show.slug, origin=pack.origin,
                             episodes=episodes, speaker_map=speaker_map)
    report = build_report(**versions, pack=pack, parses=parses, episodes=episodes, issues=issues,
                          speaker_map=speaker_map, aliases_file=Path(aliases_path).name if aliases_path else None)
    return ParseResult(show, document, report, {e.id: render_episode(e) for e in episodes})


def write_outputs(result: ParseResult, out_dir: str | Path) -> list[Path]:
    """Write show.json, parse_report.json and episodes/<id>.txt. Old renderings are
    removed first so a re-run never leaves stale files from a previous pack."""
    out = Path(out_dir)
    episodes_dir = out / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    for stale in episodes_dir.glob("*.txt"):
        stale.unlink()

    written = []
    for name, payload in (("show.json", result.show_json), ("parse_report.json", result.report)):
        target = out / name
        target.write_text(dumps(payload), encoding="utf-8")
        written.append(target)
    for episode_id, text in result.renderings.items():
        target = episodes_dir / f"{episode_id}.txt"
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written

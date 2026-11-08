"""Shared helpers for screenplay tests. Fixtures are synthetic and safe to publish."""
import hashlib
from pathlib import Path

from engine.screenplay.sources import SourceFile

FIXTURES = Path(__file__).parent / "fixtures" / "screenplays"
CLEAN_PACK = FIXTURES / "clean" / "The Lighthouse Heir"
BROKEN_PACK = FIXTURES / "broken" / "Broken Show"


def source(text: str, name: str = "synthetic-ep-001.txt") -> SourceFile:
    return SourceFile(name, "", hashlib.sha256(text.encode()).hexdigest(), text)


def fixture_source(path: Path) -> SourceFile:
    data = path.read_bytes()
    return SourceFile(path.name, "", hashlib.sha256(data).hexdigest(), data.decode("utf-8"))


def non_blank_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def codes_at(issues) -> set[tuple[str, int | None]]:
    return {(i.code, i.line) for i in issues}


MINIMAL = """EPISODE NUMBER: Episode 3
EPISODE LOGLINE: A short test episode.

--- SCRIPT START ---

SCENE 01
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 00:10.00

Actions and dialogue:

**CAMERA:**
Start: (00:00.00) | End: (00:05.00)
A wide shot.
"""

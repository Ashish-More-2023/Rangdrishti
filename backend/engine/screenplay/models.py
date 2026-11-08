"""Data model. Normalised fields sit at the top level of each object; everything
copied verbatim from the screenplay lives in a separate `source` object."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    file: str
    line: Optional[int] = None


@dataclass
class BlockSource:
    label: str                    # label exactly as written, e.g. "HOUSEKEEPER (Cold, Commanding)"
    label_line: int
    timing_line: Optional[int] = None
    start_raw: Optional[str] = None   # e.g. "00:11.30", exactly as written
    end_raw: Optional[str] = None
    text_lines: list[int] = field(default_factory=list)
    speaker_raw: Optional[str] = None


@dataclass
class Block:
    id: str
    index: int                    # 1-based position within its scene
    kind: str                     # camera | action | sound | dialogue
    speaker: Optional[str]        # canonical name (dialogue only), set by normalize
    delivery: Optional[str]       # last free-text parenthetical, e.g. "Cold, Commanding"
    voice: Optional[str]          # "V.O." | "O.S." | None (spoken on screen)
    annotations: list[str]        # other parentheticals, e.g. ["Edmund"], ["continues"]
    start_s: Optional[float]      # None when the timestamp was missing or invalid
    end_s: Optional[float]
    text: str                     # verbatim; wrapped lines joined with "\n"
    source: BlockSource


@dataclass
class SceneSource:
    marker_line: int
    marker: str                   # e.g. "SCENE 01"
    heading_line: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_raw: Optional[str] = None
    end_raw: Optional[str] = None


@dataclass
class Scene:
    id: str
    number: int
    heading: Optional[str]
    start_s: Optional[float]
    end_s: Optional[float]
    blocks: list[Block]
    source: SceneSource


@dataclass
class EpisodeSource:
    file: str
    sha256: str
    header: dict[str, str]        # every header field, keyed exactly as written
    header_number_raw: Optional[str] = None


@dataclass
class Episode:
    id: str
    number: Optional[int]
    logline: Optional[str]
    continuity_notes: Optional[str]
    duration_s: Optional[float]   # set by normalize: latest end time in the episode
    scenes: list[Scene]
    source: EpisodeSource


@dataclass
class Show:
    title: str
    slug: str
    episodes: list[Episode]

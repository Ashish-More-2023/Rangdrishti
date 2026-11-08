"""Line-by-line state machine that turns one screenplay file into an Episode.

States and what moves between them:

    HEADER      "KEY: value" lines (EPISODE NUMBER, EPISODE LOGLINE, ...)
       |  "--- SCRIPT START ---"
    PRE_SCENE   waiting for the first scene marker
       |  "SCENE 01"
    SCENE_META  "Scene heading:", "Scene start:", "Scene end:"
       |  "Actions and dialogue:"
    BODY        "**LABEL:**" opens a block, the next "Start: (..) | End: (..)" times it,
                following lines are its text. A new label, a new scene or the
                script end closes the current block.
       |  "--- SCRIPT END ---" (optional)
    AFTER_END   nothing is expected here

Every non-blank line is assigned exactly one category. A line that fits no
rule for the current state is recorded as "unaccounted" with an issue; it is
never dropped. The parser checks syntax only (shape of lines, timestamp
format). Meaning-level checks live in validate.py.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .models import Block, BlockSource, Episode, EpisodeSource, Issue, Scene, SceneSource
from .sources import SourceFile
from .timestamps import parse_timestamp


class State(Enum):
    HEADER = "header"
    PRE_SCENE = "pre_scene"
    SCENE_META = "scene_meta"
    BODY = "body"
    AFTER_END = "after_end"


# Line patterns. All are case-insensitive because packs differ in capitalisation.
SCRIPT_START = re.compile(r"^-{2,}\s*script\s+start\s*-{2,}$", re.I)
SCRIPT_END = re.compile(r"^-{2,}\s*script\s+end\s*-{2,}$", re.I)
SCENE_MARKER = re.compile(r"^scene\s+(\d+)$", re.I)
HEADER_FIELD = re.compile(r"^([A-Za-z][A-Za-z ]*?)\s*:\s*(.*)$")
SCENE_HEADING = re.compile(r"^scene\s+heading\s*:\s*(.*)$", re.I)
SCENE_START = re.compile(r"^scene\s+start\s*:\s*(.*)$", re.I)
SCENE_END = re.compile(r"^scene\s+end\s*:\s*(.*)$", re.I)
SECTION_MARKER = re.compile(r"^actions?\s+and\s+dialogues?\s*:?$", re.I)
BLOCK_LABEL = re.compile(r"^\*\*(.+?)\*\*\s*:?$")
TIMING = re.compile(r"^start\s*:\s*\(([^)]*)\)\s*\|\s*end\s*:\s*\(([^)]*)\)$", re.I)
TIMING_LIKE = re.compile(r"^start\s*:", re.I)
EPISODE_IN_FILENAME = re.compile(r"(?:episode|ep)[-_ ]*0*(\d+)", re.I)
FIRST_NUMBER = re.compile(r"(\d+)")

KNOWN_HEADER_KEYS = {
    "EPISODE NUMBER": "number",
    "EPISODE LOGLINE": "logline",
    "CONTINUITY NOTES": "continuity_notes",
}
NON_DIALOGUE_KINDS = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sound", "SFX": "sound", "SOUND": "sound"}


@dataclass
class FileParse:
    episode: Episode
    issues: list[Issue]
    line_categories: Counter
    unaccounted: list[dict]
    labels: Counter = field(default_factory=Counter)


VOICE_MARKERS = {
    "V.O.": "V.O.", "VO": "V.O.", "VOICE OVER": "V.O.", "VOICE-OVER": "V.O.",
    "O.S.": "O.S.", "OS": "O.S.", "O.C.": "O.S.", "OC": "O.S.",
    "OFF-SCREEN": "O.S.", "OFF SCREEN": "O.S.", "OFFSCREEN": "O.S.",
}
CONTINUATION_MARKERS = {"CONT'D", "CONT’D", "CONTINUES", "CONTINUING", "CONTINUED"}
PARENTHETICAL = re.compile(r"\(([^)]*)\)")


@dataclass(frozen=True)
class LabelParts:
    kind: str
    speaker_raw: Optional[str] = None
    delivery: Optional[str] = None
    voice: Optional[str] = None
    annotations: tuple[str, ...] = ()
    leftover: str = ""           # text outside the name and parentheses (should be empty)


def classify_label(label: str) -> LabelParts:
    """Split a block label into kind, speaker and the meaning of each parenthetical.

    "CAMERA"                                  -> camera
    "HOUSEKEEPER (Cold, Commanding)"          -> speaker HOUSEKEEPER, delivery "Cold, Commanding"
    "MARA (V.O.) (Reflective, Vulnerable)"    -> voice V.O., delivery "Reflective, Vulnerable"
    "LORD WREN (O.S. / Continues)"            -> voice O.S., annotation "continues"
    "HARBOR MASTER (Edmund) (Decisive)"       -> annotation "Edmund", delivery "Decisive"
    """
    key = " ".join(label.upper().split())
    if key in NON_DIALOGUE_KINDS:
        return LabelParts(NON_DIALOGUE_KINDS[key])

    name = label.split("(", 1)[0].strip()
    groups = PARENTHETICAL.findall(label)
    leftover = PARENTHETICAL.sub("", label[len(label.split("(", 1)[0]):]).strip()

    voice, notes, annotations = None, [], []
    for group in groups:
        free_text = []
        for part in (p.strip() for p in group.split("/")):
            upper = part.upper()
            if upper in VOICE_MARKERS:
                voice = VOICE_MARKERS[upper]
            elif upper in CONTINUATION_MARKERS:
                annotations.append("continues")
            elif part:
                free_text.append(part)
        if free_text:
            notes.append(" / ".join(free_text))

    delivery = notes[-1] if notes else None
    annotations = notes[:-1] + annotations
    return LabelParts("dialogue", name or label.strip(), delivery, voice, tuple(annotations), leftover)


class _EpisodeParser:
    def __init__(self, source: SourceFile):
        self.file = source.name
        self.source = source
        self.state = State.HEADER
        self.header: dict[str, str] = {}
        self.header_key: Optional[str] = None
        self.scenes: list[Scene] = []
        self.block: Optional[Block] = None
        self.issues: list[Issue] = []
        self.categories: Counter = Counter()
        self.unaccounted: list[dict] = []
        self.labels: Counter = Counter()

    # ---- bookkeeping -------------------------------------------------------
    def issue(self, severity: str, code: str, message: str, line: Optional[int] = None) -> None:
        self.issues.append(Issue(severity, code, message, self.file, line))

    def account(self, category: str) -> None:
        self.categories[category] += 1

    def reject(self, lineno: int, text: str, reason: str) -> None:
        self.account("unaccounted")
        self.unaccounted.append({"file": self.file, "line": lineno, "state": self.state.value, "text": text})
        self.issue("error", "unrecognized_line", f"{reason}: {text[:80]!r}", lineno)

    def timestamp(self, raw: str, lineno: int, what: str) -> Optional[float]:
        value = parse_timestamp(raw)
        if value is None:
            self.issue("error", "invalid_timestamp", f"{what} {raw!r} is not a valid timestamp", lineno)
        return value

    # ---- block and scene lifecycle -----------------------------------------
    def close_block(self) -> None:
        block = self.block
        if block is None:
            return
        if block.source.timing_line is None:
            self.issue("error", "block_missing_timing", f"Block {block.source.label!r} has no Start/End line", block.source.label_line)
        if not block.source.text_lines:
            self.issue("warning", "empty_block_text", f"Block {block.source.label!r} has no text", block.source.label_line)
        self.block = None

    def open_scene(self, number: int, lineno: int, marker: str) -> None:
        self.close_block()
        self.scenes.append(Scene("", number, None, None, None, [], SceneSource(lineno, marker)))
        self.state = State.SCENE_META

    def open_block(self, label: str, lineno: int) -> None:
        self.close_block()
        scene = self.scenes[-1]
        parts = classify_label(label)
        if parts.leftover:
            self.issue("warning", "unusual_label", f"Text outside parentheses in label {label!r}", lineno)
        self.labels[parts.speaker_raw if parts.kind == "dialogue" else label.upper()] += 1
        self.block = Block(
            id="", index=len(scene.blocks) + 1, kind=parts.kind, speaker=None,
            delivery=parts.delivery, voice=parts.voice, annotations=list(parts.annotations),
            start_s=None, end_s=None, text="",
            source=BlockSource(label=label, label_line=lineno, speaker_raw=parts.speaker_raw),
        )
        scene.blocks.append(self.block)

    # ---- per-state handlers ------------------------------------------------
    def on_header(self, line: str, lineno: int) -> None:
        match = HEADER_FIELD.match(line)
        if match and match.group(1) == match.group(1).upper():
            key = " ".join(match.group(1).upper().split())
            self.header[key] = match.group(2).strip()
            self.header_key = key
            self.account("header_field")
            if key not in KNOWN_HEADER_KEYS:
                self.issue("info", "unknown_header_field", f"Kept unknown header field {key!r}", lineno)
        elif self.header_key:
            self.header[self.header_key] += "\n" + line
            self.account("header_continuation")
        else:
            self.reject(lineno, line, "Line before any header field")

    def on_scene_meta(self, line: str, lineno: int) -> None:
        scene = self.scenes[-1]
        if m := SCENE_HEADING.match(line):
            scene.heading, scene.source.heading_line = m.group(1).strip(), lineno
        elif m := SCENE_START.match(line):
            scene.source.start_raw, scene.source.start_line = m.group(1).strip(), lineno
            scene.start_s = self.timestamp(scene.source.start_raw, lineno, "Scene start")
        elif m := SCENE_END.match(line):
            scene.source.end_raw, scene.source.end_line = m.group(1).strip(), lineno
            scene.end_s = self.timestamp(scene.source.end_raw, lineno, "Scene end")
        elif SECTION_MARKER.match(line):
            self.state = State.BODY
            self.account("section_marker")
            return
        elif m := BLOCK_LABEL.match(line):
            self.issue("warning", "missing_section_marker", "Block starts without an 'Actions and dialogue:' line", lineno)
            self.state = State.BODY
            self.on_body(line, lineno)
            return
        else:
            self.reject(lineno, line, "Unexpected line in scene header")
            return
        self.account("scene_meta")

    def on_body(self, line: str, lineno: int) -> None:
        block = self.block
        if m := BLOCK_LABEL.match(line):
            self.open_block(m.group(1).strip().rstrip(":").strip(), lineno)
            self.account("block_label")
        elif TIMING_LIKE.match(line):
            if block is None or block.source.timing_line is not None or block.source.text_lines:
                self.reject(lineno, line, "Start/End line with no block waiting for one")
                return
            block.source.timing_line = lineno
            self.account("block_timing")
            m = TIMING.match(line)
            if not m:
                self.issue("error", "malformed_timing_line", f"Cannot read Start/End from {line!r}", lineno)
                return
            block.source.start_raw, block.source.end_raw = m.group(1).strip(), m.group(2).strip()
            block.start_s = self.timestamp(block.source.start_raw, lineno, "Block start")
            block.end_s = self.timestamp(block.source.end_raw, lineno, "Block end")
        elif block is not None:
            if block.source.timing_line is None and not block.source.text_lines:
                self.issue("error", "text_before_timing", f"Text appears before the Start/End line of {block.source.label!r}", lineno)
            block.text = f"{block.text}\n{line}" if block.text else line
            block.source.text_lines.append(lineno)
            self.account("block_text")
        else:
            self.reject(lineno, line, "Line before the first block of a scene")

    # ---- main loop ---------------------------------------------------------
    def feed(self, raw_line: str, lineno: int) -> None:
        line = raw_line.strip()
        if not line:
            return

        if SCRIPT_START.match(line):
            if self.state is not State.HEADER:
                self.issue("warning", "unexpected_script_start", "Repeated or late SCRIPT START marker", lineno)
            self.state = State.PRE_SCENE
            self.account("script_marker")
            return
        if SCRIPT_END.match(line):
            self.close_block()
            self.state = State.AFTER_END
            self.account("script_marker")
            return
        if (m := SCENE_MARKER.match(line)) and self.state is not State.AFTER_END:
            if self.state is State.HEADER:
                self.issue("warning", "missing_script_start", "Scene begins without a SCRIPT START marker", lineno)
            self.open_scene(int(m.group(1)), lineno, line)
            self.account("scene_marker")
            return

        if self.state is State.HEADER:
            self.on_header(line, lineno)
        elif self.state is State.SCENE_META:
            self.on_scene_meta(line, lineno)
        elif self.state is State.BODY:
            self.on_body(line, lineno)
        elif self.state is State.PRE_SCENE:
            self.reject(lineno, line, "Line between SCRIPT START and the first scene")
        else:
            self.reject(lineno, line, "Line after SCRIPT END")

    # ---- finish ------------------------------------------------------------
    def episode_number(self) -> tuple[Optional[int], Optional[str]]:
        raw = self.header.get("EPISODE NUMBER")
        if raw and (m := FIRST_NUMBER.search(raw)):
            return int(m.group(1)), raw
        if m := EPISODE_IN_FILENAME.search(self.file):
            self.issue("warning", "episode_number_from_filename", "No usable EPISODE NUMBER header; using the file name", None)
            return int(m.group(1)), raw
        self.issue("error", "episode_number_missing", "No episode number in header or file name", None)
        return None, raw

    def finish(self, ordinal: int) -> FileParse:
        self.close_block()
        if self.state is State.HEADER:
            self.issue("error", "no_script_body", "File has no SCRIPT START marker or scenes", None)
        elif not self.scenes:
            self.issue("error", "no_scenes", "File has no scenes", None)

        number, number_raw = self.episode_number()
        episode = Episode(
            id="", number=number,
            logline=self.header.get("EPISODE LOGLINE"),
            continuity_notes=self.header.get("CONTINUITY NOTES"),
            duration_s=None, scenes=self.scenes,
            source=EpisodeSource(self.file, self.source.sha256, dict(self.header), number_raw),
        )
        assign_ids(episode, ordinal)
        return FileParse(episode, self.issues, self.categories, self.unaccounted, self.labels)


def assign_ids(episode: Episode, ordinal: int) -> None:
    """IDs come from the screenplay's own numbering, so they stay the same across
    runs and do not shift when other episodes are added. Only if the episode number
    is missing does the file's position in the pack stand in (flagged as an error)."""
    episode.id = f"E{episode.number:03d}" if episode.number is not None else f"EX{ordinal:03d}"
    for scene in episode.scenes:
        scene.id = f"{episode.id}-S{scene.number:02d}"
        for block in scene.blocks:
            block.id = f"{scene.id}-B{block.index:03d}"


def parse_episode(source: SourceFile, ordinal: int = 0) -> FileParse:
    parser = _EpisodeParser(source)
    if source.text is None:
        parser.issue("error", "unreadable_file", source.decode_error or "Could not decode file", None)
        return parser.finish(ordinal)
    for lineno, raw_line in enumerate(source.text.splitlines(), start=1):
        parser.feed(raw_line, lineno)
    return parser.finish(ordinal)

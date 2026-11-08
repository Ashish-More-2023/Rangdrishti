"""Read-only, indexed view of a parsed show.json.

Later stages (candidate discovery, validation, AI judging) read show.json through
this module instead of re-parsing screenplays, so each stage depends only on the
previous stage's versioned output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SUPPORTED_SCHEMA_MAJOR = "1"


@dataclass(frozen=True)
class IndexedBlock:
    id: str
    episode_id: str
    scene_id: str
    kind: str                       # camera | action | sound | dialogue
    speaker: Optional[str]
    delivery: Optional[str]
    voice: Optional[str]
    start_s: Optional[float]
    end_s: Optional[float]
    text: str
    start_raw: Optional[str]
    end_raw: Optional[str]

    @property
    def is_timed(self) -> bool:
        return self.start_s is not None and self.end_s is not None


@dataclass(frozen=True)
class IndexedScene:
    id: str
    episode_id: str
    number: int
    heading: Optional[str]
    start_s: Optional[float]
    end_s: Optional[float]


@dataclass(frozen=True)
class IndexedEpisode:
    id: str
    number: Optional[int]
    duration_s: Optional[float]
    scenes: tuple[IndexedScene, ...]
    blocks: tuple[IndexedBlock, ...]   # sorted by (start, end, id); untimed blocks last

    @property
    def untimed_blocks(self) -> tuple[IndexedBlock, ...]:
        return tuple(b for b in self.blocks if not b.is_timed)


@dataclass(frozen=True)
class ShowIndex:
    title: str
    slug: str
    schema_version: str
    episodes: dict[str, IndexedEpisode]   # in episode order
    blocks: dict[str, IndexedBlock]
    scenes: dict[str, IndexedScene]

    @classmethod
    def from_show_json(cls, document: dict) -> "ShowIndex":
        version = str(document.get("schema_version", ""))
        if version.split(".")[0] != SUPPORTED_SCHEMA_MAJOR:
            raise ValueError(f"Unsupported show.json schema_version {version!r}; expected {SUPPORTED_SCHEMA_MAJOR}.x")

        episodes, blocks, scenes = {}, {}, {}
        for ep in document["episodes"]:
            ep_scenes, ep_blocks = [], []
            for sc in ep["scenes"]:
                scene = IndexedScene(sc["id"], ep["id"], sc["number"], sc.get("heading"), sc.get("start_s"), sc.get("end_s"))
                ep_scenes.append(scene)
                scenes[scene.id] = scene
                for b in sc["blocks"]:
                    source = b.get("source") or {}
                    block = IndexedBlock(
                        b["id"], ep["id"], sc["id"], b["kind"], b.get("speaker"), b.get("delivery"), b.get("voice"),
                        b.get("start_s"), b.get("end_s"), b.get("text", ""), source.get("start_raw"), source.get("end_raw"),
                    )
                    ep_blocks.append(block)
                    blocks[block.id] = block
            ep_blocks.sort(key=lambda b: (not b.is_timed, b.start_s or 0.0, b.end_s or 0.0, b.id))
            episodes[ep["id"]] = IndexedEpisode(ep["id"], ep.get("number"), ep.get("duration_s"), tuple(ep_scenes), tuple(ep_blocks))

        show = document.get("show", {})
        return cls(show.get("title", ""), show.get("slug", ""), version, episodes, blocks, scenes)

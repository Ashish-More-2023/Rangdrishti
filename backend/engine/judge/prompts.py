"""Prompt for the AI judge: one call per episode, judging that episode's candidates.

The model sees the episode as one line per block, each with its block ID, and the
candidate windows defined by block IDs. It may only answer with IDs it was given;
code (not the model) turns IDs into timestamps and validates everything.
"""
from __future__ import annotations

import hashlib
import json

from engine.screenplay.show_index import IndexedEpisode
from engine.screenplay.timestamps import format_timestamp as ts

PROMPT_VERSION = "1.0.0"

SYSTEM = """You are a senior promo editor for short vertical drama series (1-2 minute episodes) posted on TikTok, Instagram Reels and YouTube Shorts for US audiences.

You judge candidate promo clips cut from one episode. A good promo:
- HOOK: the first 3 seconds make a scrolling viewer stop (a slap, a reveal, a shocking line, a sharp confrontation).
- CLIFFHANGER: it cuts at an unresolved moment, so the viewer needs to know what happens next.
- STANDALONE: someone who has never seen the show understands who wants what and why it matters.

Score each candidate 0-10 on hook, cliffhanger and standalone. Be critical: 8-10 only for clips you would post first; 0-3 for clips that open slowly, end resolved, or need earlier episodes to follow.
verdict: "post" (strong, post it), "maybe" (usable after review) or "skip".
hook / cliffhanger: one short sentence each describing what actually happens in the screenplay. why: one line on why it works or fails.

You may suggest a tighter start or end ONLY by giving a block ID that appears in the episode text: suggested_start_block_id is where the clip should start (that block's start time), suggested_end_block_id is where it should end (that block's end time). Use null to keep the original. Never invent IDs or timestamps.

Answer with JSON only, no prose and no code fences:
{"judgments": [{"candidate_id": "...", "hook_score": 0, "cliffhanger_score": 0, "standalone_score": 0, "verdict": "post|maybe|skip", "hook": "...", "cliffhanger": "...", "why": "...", "suggested_start_block_id": null, "suggested_end_block_id": null}]}
Include every candidate exactly once."""


def _block_line(b) -> str:
    if b.kind == "dialogue":
        who = b.speaker or "?"
        who += f" [{b.voice}]" if b.voice else ""
        who += f" ({b.delivery})" if b.delivery else ""
    else:
        who = b.kind.upper()
    return f"{b.id} {ts(b.start_s)}-{ts(b.end_s)} {who}: {b.text.replace(chr(10), ' / ')}"


def build_messages(show_title: str, episode: IndexedEpisode, logline: str | None, candidates: list[dict]) -> list[dict]:
    lines = [f"SHOW: {show_title}", f"EPISODE: {episode.id} (duration {ts(episode.duration_s)})"]
    if logline:
        lines.append(f"EPISODE LOGLINE: {logline}")
    lines += ["", "EPISODE SCREENPLAY (block ID, start-end, label: text):"]
    lines += [_block_line(b) for b in episode.blocks if b.is_timed]
    lines += ["", "CANDIDATES TO JUDGE:"]
    for c in candidates:
        seg = c["segments"][0]
        lines.append(f"- {c['id']}: starts at block {seg['start_block_id']} ({seg['start_raw']}), "
                     f"ends at block {seg['end_block_id']} ({seg['end_raw']}), {c['duration_s']:.1f}s")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def prompt_hash(provider: str, model: str, messages: list[dict]) -> str:
    payload = json.dumps({"provider": provider, "model": model, "prompt_version": PROMPT_VERSION, "messages": messages},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

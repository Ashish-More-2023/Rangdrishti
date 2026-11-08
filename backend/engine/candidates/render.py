"""Turn scored windows into the candidates.json records and the human review file."""
from __future__ import annotations

from engine.screenplay.show_index import ShowIndex
from engine.screenplay.timestamps import format_timestamp as ts

from .scoring import ScoredWindow

FEATURE_ORDER = ("hook", "cliffhanger", "dialogue_density", "intensity", "standalone", "duration_fit")


def promo_segments(s: ScoredWindow) -> list[dict]:
    w = s.window
    return [{
        "episode_id": w.episode_id,
        "start_s": w.start.t, "end_s": w.end.t,
        "start_raw": w.start.raw, "end_raw": w.end.raw,
        "start_block_id": w.start.block_id, "start_block_edge": w.start.edge,
        "end_block_id": w.end.block_id, "end_block_edge": w.end.edge,
    }]


def _preview(index: ShowIndex, block_id: str | None) -> dict | None:
    if not block_id:
        return None
    b = index.blocks[block_id]
    return {"block_id": b.id, "speaker": b.speaker, "delivery": b.delivery, "text": b.text}


def candidate_record(s: ScoredWindow, index: ShowIndex, config: dict, episode_rank: int) -> dict:
    episode = index.episodes[s.window.episode_id]
    breakdown = {
        name: {
            "value": s.features[name].value,
            "weight": config["weights"][name],
            "contribution": round(config["weights"][name] * s.features[name].value, 4),
            "keyword_bonus": s.features[name].keyword_bonus,
            "reasons": list(s.features[name].reasons),
            "evidence_block_ids": list(s.features[name].evidence),
        }
        for name in FEATURE_ORDER
    }
    hook_ev, cliff_ev = s.features["hook"].evidence, s.features["cliffhanger"].evidence
    return {
        "id": s.window.id,
        "rank": None,                      # filled in after show-wide ranking
        "episode_rank": episode_rank,
        "episode_id": episode.id,
        "episode_number": episode.number,
        "segments": promo_segments(s),
        "duration_s": s.window.duration_s,
        "score": s.score,
        "score_breakdown": breakdown,
        "scene_crossing": {"count": s.scene_crossings, "penalty": s.penalty},
        "flags": list(s.flags),
        "block_ids": list(s.block_ids),
        "scene_ids": list(s.scene_ids),
        "trimmed_block_ids": list(s.trimmed_block_ids),
        "hook_line": _preview(index, hook_ev[0] if hook_ev else None),
        "cliffhanger_line": _preview(index, cliff_ev[0] if cliff_ev else None),
    }


def _block_line(index: ShowIndex, block_id: str) -> str:
    b = index.blocks[block_id]
    who = b.kind.upper() if b.kind != "dialogue" else f"{b.speaker}{' [' + b.voice + ']' if b.voice else ''}" + (f" ({b.delivery})" if b.delivery else "")
    return f"    {b.id} {ts(b.start_s)}-{ts(b.end_s)} {who}: {b.text.replace(chr(10), ' / ')}"


def review_markdown(records: list[dict], index: ShowIndex, meta: dict) -> str:
    out = [
        f"# Promo candidates: {index.title}",
        "",
        f"Rule-based shortlist (no AI). Config {meta['config_version']}, {len(records)} candidates.",
        "Each candidate shows its score breakdown and the full screenplay text inside the clip.",
        "These are suggestions for review, not final promos.",
    ]
    by_episode: dict[str, list[dict]] = {}
    for r in records:
        by_episode.setdefault(r["episode_id"], []).append(r)
    for episode_id, items in by_episode.items():
        out += ["", f"## {episode_id}"]
        for r in sorted(items, key=lambda x: x["episode_rank"]):
            seg = r["segments"][0]
            out += ["", f"### #{r['rank']} {r['id']}  {seg['start_raw']}-{seg['end_raw']} ({r['duration_s']:.1f}s)  score {r['score']:.3f}"]
            if r["flags"]:
                out.append(f"Flags: {', '.join(r['flags'])}")
            for name in FEATURE_ORDER:
                f = r["score_breakdown"][name]
                out.append(f"- {name} {f['value']:.2f} x {f['weight']:.2f} = {f['contribution']:.3f}: {'; '.join(f['reasons'])}")
            if r["scene_crossing"]["count"]:
                out.append(f"- scene crossing penalty -{r['scene_crossing']['penalty']:.3f}")
            out += ["", "```"] + [_block_line(index, bid).strip() for bid in r["block_ids"]] + ["```"]
    return "\n".join(out) + "\n"

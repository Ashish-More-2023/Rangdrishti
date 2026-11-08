"""Apply suggested trims (validated) and combine rule and AI scores into the final ranking."""
from __future__ import annotations

from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig, validate_promo

from .parse import Judgment


def ai_score(j: Judgment, subweights: dict) -> float:
    return round((subweights["hook"] * j.hook_score + subweights["cliffhanger"] * j.cliffhanger_score
                  + subweights["standalone"] * j.standalone_score) / 10, 4)


def try_trim(candidate: dict, j: Judgment, index: ShowIndex, rules: RuleConfig, min_overlap: float) -> tuple[dict, dict]:
    """Return (segment to use, trim record). The original is kept unless the trim passes every hard rule."""
    original = candidate["segments"][0]
    if not (j.suggested_start_block_id or j.suggested_end_block_id):
        return original, {"suggested": False, "applied": False}

    seg = dict(original)
    for which, block_id, edge in (("start", j.suggested_start_block_id, "start"), ("end", j.suggested_end_block_id, "end")):
        if not block_id:
            continue
        block = index.blocks.get(block_id)
        if block is None or block.episode_id != original["episode_id"]:
            return original, {"suggested": True, "applied": False, "reason": f"{which} block {block_id!r} is not in this episode"}
        seg.update({f"{which}_s": getattr(block, f"{edge}_s"), f"{which}_raw": getattr(block, f"{edge}_raw"),
                    f"{which}_block_id": block.id, f"{which}_block_edge": edge})

    violations = validate_promo({"segments": [seg]}, index, rules)
    if violations:
        return original, {"suggested": True, "applied": False, "reason": "; ".join(sorted({v.code for v in violations}))}
    shared = min(seg["end_s"], original["end_s"]) - max(seg["start_s"], original["start_s"])
    if shared / min(seg["end_s"] - seg["start_s"], original["end_s"] - original["start_s"]) < min_overlap:
        return original, {"suggested": True, "applied": False, "reason": "moves too far from the original clip"}
    if seg == original:
        return original, {"suggested": True, "applied": False, "reason": "same as original"}
    return seg, {"suggested": True, "applied": True, "original": original}

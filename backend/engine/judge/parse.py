"""Turn the model's raw text into validated judgments. Nothing is guessed or repaired:
anything malformed is reported and that candidate falls back to its rule score."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

VERDICTS = ("post", "maybe", "skip")
TEXT_LIMIT = 300
FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


@dataclass(frozen=True)
class Judgment:
    candidate_id: str
    hook_score: float
    cliffhanger_score: float
    standalone_score: float
    verdict: str
    hook: str
    cliffhanger: str
    why: str
    suggested_start_block_id: Optional[str]
    suggested_end_block_id: Optional[str]


@dataclass
class ParseResult:
    judgments: dict[str, Judgment] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)      # {"code", "candidate_id"?, "detail"}
    fatal: Optional[str] = None                             # set when nothing could be read


def extract_json(text: str) -> Optional[dict]:
    cleaned = FENCE.sub("", text.strip())
    for candidate in (cleaned, cleaned[cleaned.find("{"): cleaned.rfind("}") + 1] if "{" in cleaned else ""):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


def _score(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
        return None
    return float(value)


def _text(value) -> Optional[str]:
    return value.strip()[:TEXT_LIMIT] if isinstance(value, str) and value.strip() else None


def _block_id(value) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_judgments(text: str, expected_ids: list[str]) -> ParseResult:
    result = ParseResult()
    data = extract_json(text)
    if data is None or not isinstance(data.get("judgments"), list):
        result.fatal = "response is not JSON with a 'judgments' list"
        return result

    expected = set(expected_ids)
    for item in data["judgments"]:
        cid = item.get("candidate_id") if isinstance(item, dict) else None
        if cid not in expected:
            result.issues.append({"code": "unknown_candidate", "candidate_id": cid, "detail": "ID was not offered"})
            continue
        if cid in result.judgments:
            result.issues.append({"code": "duplicate_judgment", "candidate_id": cid, "detail": "kept the first"})
            continue
        scores = {k: _score(item.get(k)) for k in ("hook_score", "cliffhanger_score", "standalone_score")}
        verdict = str(item.get("verdict", "")).strip().lower()
        texts = {k: _text(item.get(k)) for k in ("hook", "cliffhanger", "why")}
        bad = [k for k, v in {**scores, **texts}.items() if v is None] + ([] if verdict in VERDICTS else ["verdict"])
        if bad:
            result.issues.append({"code": "invalid_fields", "candidate_id": cid, "detail": ", ".join(bad)})
            continue
        result.judgments[cid] = Judgment(cid, scores["hook_score"], scores["cliffhanger_score"], scores["standalone_score"],
                                         verdict, texts["hook"], texts["cliffhanger"], texts["why"],
                                         _block_id(item.get("suggested_start_block_id")), _block_id(item.get("suggested_end_block_id")))
    for cid in expected_ids:
        if cid not in result.judgments and not any(i.get("candidate_id") == cid for i in result.issues):
            result.issues.append({"code": "not_judged", "candidate_id": cid, "detail": "missing from the response"})
    return result

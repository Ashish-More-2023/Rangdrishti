"""Run the AI judge over every episode's candidates and produce the final ranked promos."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.ai import ProviderError, ProviderRequest
from engine.candidates.report import distribution
from engine.screenplay.show_index import ShowIndex
from engine.validation.promo_rules import RuleConfig, validate_promo

from .combine import ai_score, try_trim
from .parse import parse_judgments
from .prompts import PROMPT_VERSION, build_messages, prompt_hash

JUDGE_SCHEMA_VERSION = "1.0.0"
DEFAULT_CONFIG = Path(__file__).with_name("judge_config.json")
CSV_FIELDS = ["rank", "post_first_rank", "promo_id", "episode_id", "start", "end", "duration_s", "final_score",
              "rule_score", "ai_score", "verdict", "hook", "cliffhanger", "why", "trimmed", "judged"]


@dataclass
class JudgeResult:
    promos: dict
    report: dict
    csv_text: str

    @property
    def failed_episodes(self) -> list[str]:
        return self.report["calls"]["failed_episodes"]


def load_judge_config(path: Optional[str | Path] = None) -> dict:
    cfg = json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    if abs(cfg["rule_weight"] + cfg["ai_weight"] - 1) > 1e-6 or abs(sum(cfg["ai_subweights"].values()) - 1) > 1e-6:
        raise ValueError("judge_config weights must each sum to 1")
    return cfg


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _fingerprint(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _call_or_cache(provider, messages, candidate_ids, raw_dir: Path, episode_id: str, refresh: bool, budget: dict):
    """Return (raw_text or None, status). Every live response is saved verbatim before it is parsed."""
    key = prompt_hash(provider.name, provider.model, messages)
    raw_file = raw_dir / f"{episode_id}-{key[:12]}.json"
    if raw_file.exists() and not refresh:
        return json.loads(raw_file.read_text(encoding="utf-8"))["response_text"], "cache"
    if budget["remaining"] is not None and budget["remaining"] <= 0:
        return None, "skipped_call_limit"
    if budget["remaining"] is not None:
        budget["remaining"] -= 1
    try:
        response = provider.complete(ProviderRequest(messages, tuple(candidate_ids)))
    except ProviderError as exc:
        return None, f"provider_error: {exc}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file.write_text(json.dumps({
        "episode_id": episode_id, "provider": provider.name, "model": provider.model,
        "response_model": response.model, "prompt_version": PROMPT_VERSION, "prompt_sha256": key,
        "messages": messages, "response_text": response.text, "usage": response.usage,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return response.text, "live"


def judge_show(show_doc: dict, candidates_doc: dict, provider, config: dict, raw_dir: Path,
               episodes: Optional[set[str]] = None, refresh: bool = False, max_calls: Optional[int] = None) -> JudgeResult:
    index = ShowIndex.from_show_json(show_doc)
    loglines = {e["id"]: e.get("logline") for e in show_doc["episodes"]}
    rules = RuleConfig()
    by_episode: dict[str, list[dict]] = {}
    for c in candidates_doc["candidates"]:
        by_episode.setdefault(c["episode_id"], []).append(c)

    budget = {"remaining": max_calls}
    statuses, issues, judgments = {}, [], {}
    for episode_id, cands in by_episode.items():
        if episodes and episode_id not in episodes:
            statuses[episode_id] = "not_requested"
            continue
        cands = sorted(cands, key=lambda c: c["episode_rank"])
        messages = build_messages(index.title, index.episodes[episode_id], loglines.get(episode_id), cands)
        text, status = _call_or_cache(provider, messages, [c["id"] for c in cands], raw_dir, episode_id, refresh, budget)
        if text is not None:
            parsed = parse_judgments(text, [c["id"] for c in cands])
            if parsed.fatal:
                status = f"unreadable_response: {parsed.fatal}"
            judgments.update(parsed.judgments)
            issues += [{**i, "episode_id": episode_id} for i in parsed.issues]
        statuses[episode_id] = status

    # ---- combine, trim, validate ------------------------------------------------
    rows = []
    trim_counts = Counter()
    for c in candidates_doc["candidates"]:
        j = judgments.get(c["id"])
        if j:
            seg, trim = try_trim(c, j, index, rules, config["trim"]["min_overlap_with_original"]) if config["trim"]["allowed"] \
                else (c["segments"][0], {"suggested": False, "applied": False})
            a = ai_score(j, config["ai_subweights"])
            final = round(config["rule_weight"] * c["score"] + config["ai_weight"] * a, 4)
            ai = {"hook_score": j.hook_score, "cliffhanger_score": j.cliffhanger_score, "standalone_score": j.standalone_score,
                  "verdict": j.verdict, "hook": j.hook, "cliffhanger": j.cliffhanger, "why": j.why}
        else:
            seg, trim, a, final, ai = c["segments"][0], {"suggested": False, "applied": False}, None, None, None
        trim_counts["applied" if trim.get("applied") else trim.get("reason", "none") if trim.get("suggested") else "not_suggested"] += 1
        rows.append({"candidate": c, "segment": seg, "trim": trim, "ai_score": a, "final": final, "ai": ai})

    judged = sorted((r for r in rows if r["ai"]), key=lambda r: (-r["final"], r["candidate"]["rank"]))
    unjudged = sorted((r for r in rows if not r["ai"]), key=lambda r: r["candidate"]["rank"])
    pf, pf_rank, per_ep = config["post_first"], {}, Counter()
    for r in judged:
        if len(pf_rank) >= pf["count"]:
            break
        ep = r["candidate"]["episode_id"]
        if r["ai"]["verdict"] in pf["exclude_verdicts"] or per_ep[ep] >= pf["max_per_episode"]:
            continue
        per_ep[ep] += 1
        pf_rank[r["candidate"]["id"]] = len(pf_rank) + 1

    promos, failures = [], []
    for rank, r in enumerate(judged + unjudged, start=1):
        c, seg = r["candidate"], r["segment"]
        record = {
            "rank": rank, "post_first_rank": pf_rank.get(c["id"]), "id": c["id"], "episode_id": c["episode_id"],
            "segments": [seg], "duration_s": round(seg["end_s"] - seg["start_s"], 3),
            "final_score": r["final"], "rule_score": c["score"], "rule_rank": c["rank"], "ai_score": r["ai_score"],
            "judged": r["ai"] is not None, "ai": r["ai"], "trim": r["trim"], "flags": c["flags"],
            "block_ids": c["block_ids"] if not r["trim"].get("applied") else None,
        }
        if validate_promo({"segments": [seg]}, index, rules):
            failures.append(c["id"])
        promos.append(record)

    first = sorted((p for p in promos if p["post_first_rank"]), key=lambda p: p["post_first_rank"])
    meta = {"provider": provider.name, "model": provider.model, "prompt_version": PROMPT_VERSION,
            "judge_config_version": config["config_version"]}
    promos_doc = {"schema_version": JUDGE_SCHEMA_VERSION, **meta,
                  "candidates_sha256": _fingerprint(candidates_doc), "show": candidates_doc["show"],
                  "post_first": [{"post_first_rank": p["post_first_rank"], "id": p["id"], "episode_id": p["episode_id"],
                                  "segments": p["segments"], "hook": p["ai"]["hook"], "cliffhanger": p["ai"]["cliffhanger"],
                                  "why": p["ai"]["why"], "final_score": p["final_score"]} for p in first],
                  "promos": promos}

    status_counts = Counter(s.split(":")[0] for s in statuses.values())
    report = {
        "schema_version": JUDGE_SCHEMA_VERSION, **meta,
        "mock_warning": "MOCK PROVIDER: scores are placeholders, not judgements" if provider.name == "mock" else None,
        "calls": {"by_status": dict(sorted(status_counts.items())),
                  "failed_episodes": sorted(e for e, s in statuses.items() if s.startswith(("provider_error", "unreadable"))),
                  "skipped_by_call_limit": sorted(e for e, s in statuses.items() if s == "skipped_call_limit"),
                  "episode_status": dict(sorted(statuses.items()))},
        "counts": {"candidates": len(rows), "judged": len(judged), "unjudged": len(unjudged), "post_first": len(first),
                   "verdicts": dict(sorted(Counter(r["ai"]["verdict"] for r in judged).items()))},
        "parse_issues": {"by_code": dict(sorted(Counter(i["code"] for i in issues).items())), "items": issues},
        "trims": dict(sorted(trim_counts.items())),
        "scores": {"final": distribution([r["final"] for r in judged]), "ai": distribution([r["ai_score"] for r in judged])},
        "rank_changes": {"top10_rule_ids_still_in_top10": len({p["id"] for p in promos[:10]} & {c["id"] for c in candidates_doc["candidates"][:10]})},
        "validation": {"promos_checked": len(promos), "promos_failing": failures},
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for p in promos:
        s = p["segments"][0]
        writer.writerow({"rank": p["rank"], "post_first_rank": p["post_first_rank"] or "", "promo_id": p["id"],
                         "episode_id": p["episode_id"], "start": s["start_raw"], "end": s["end_raw"],
                         "duration_s": p["duration_s"], "final_score": p["final_score"] if p["final_score"] is not None else "",
                         "rule_score": p["rule_score"], "ai_score": p["ai_score"] if p["ai_score"] is not None else "",
                         "verdict": p["ai"]["verdict"] if p["ai"] else "", "hook": p["ai"]["hook"] if p["ai"] else "",
                         "cliffhanger": p["ai"]["cliffhanger"] if p["ai"] else "", "why": p["ai"]["why"] if p["ai"] else "",
                         "trimmed": "yes" if p["trim"].get("applied") else "", "judged": "yes" if p["judged"] else "no"})
    return JudgeResult(promos_doc, report, buf.getvalue())


def write_outputs(result: JudgeResult, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"promos.json": json.dumps(result.promos, indent=2, ensure_ascii=False) + "\n",
             "judge_report.json": json.dumps(result.report, indent=2, ensure_ascii=False) + "\n",
             "promos.csv": result.csv_text}
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8-sig" if name.endswith(".csv") else "utf-8")
    return [out_dir / n for n in files]


def raw_dir_for(data_dir: Path, slug: str, provider) -> Path:
    return data_dir / "raw_outputs" / slug / _safe(f"{provider.name}-{provider.model}")

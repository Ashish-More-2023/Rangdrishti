"""Stage 2: rule-based promo candidate discovery (deterministic, no AI).

    timeline   clean cut points (never inside a spoken line or a camera shot)
    windows    every continuous 20-60 s window between clean cuts, one episode at a time
    features   six explainable features; structure first, keywords only a capped bonus
    scoring    weighted sum minus a scene-crossing penalty
    select     up to N diverse candidates per episode (overlap rule, ending cap, min score)
    render     candidates.json records and the human review file
    pipeline   runs it all and validates every window with engine.validation.promo_rules
"""
from .config import load_config
from .pipeline import CANDIDATES_SCHEMA_VERSION, CandidateResult, find_candidates, write_outputs

__all__ = ["CANDIDATES_SCHEMA_VERSION", "CandidateResult", "find_candidates", "load_config", "write_outputs"]

"""Stage 3: an AI judges the rule-based candidates; code validates and ranks.

    prompts   one prompt per episode: the episode as block-ID lines + its candidates
    parse     strict reading of the model's JSON; malformed answers are reported, never repaired
    combine   validated trims + final score = rule_weight*rule + ai_weight*ai
    pipeline  caching, raw-output logging, ranking, "post first" list, exports
"""
from .pipeline import JUDGE_SCHEMA_VERSION, JudgeResult, judge_show, load_judge_config, write_outputs

__all__ = ["JUDGE_SCHEMA_VERSION", "JudgeResult", "judge_show", "load_judge_config", "write_outputs"]

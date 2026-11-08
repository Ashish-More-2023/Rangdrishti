"""Load and sanity-check the candidate configuration.

The config is data, not code: weights, thresholds and vocabulary can change
without touching the logic, and its version and hash are stamped on every output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_PATH = Path(__file__).with_name("candidates_config.json")
FEATURE_NAMES = ("hook", "cliffhanger", "dialogue_density", "intensity", "standalone", "duration_fit")
REQUIRED_SECTIONS = ("config_version", "window", "weights", "keyword_bonus_max", "scene_crossing", "hook",
                     "cliffhanger", "dialogue_density", "intensity", "standalone", "duration_fit", "selection", "vocabulary")
MAX_KEYWORD_BONUS = 0.25   # keywords may only ever be a small bonus on top of structural evidence


class ConfigError(ValueError):
    pass


def config_hash(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_config(config: dict) -> dict:
    missing = [s for s in REQUIRED_SECTIONS if s not in config]
    if missing:
        raise ConfigError(f"Config is missing sections: {missing}")

    weights = config["weights"]
    if set(weights) != set(FEATURE_NAMES):
        raise ConfigError(f"weights must have exactly {list(FEATURE_NAMES)}")
    if any(w < 0 for w in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ConfigError(f"weights must be non-negative and sum to 1.0 (got {sum(weights.values()):.4f})")

    if not 0 <= config["keyword_bonus_max"] <= MAX_KEYWORD_BONUS:
        raise ConfigError(f"keyword_bonus_max must be between 0 and {MAX_KEYWORD_BONUS}")

    window = config["window"]
    if not 0 < window["min_duration_s"] < window["max_duration_s"]:
        raise ConfigError("window.min_duration_s must be positive and below max_duration_s")

    sel = config["selection"]
    if sel["per_episode"] < 1 or not 0 < sel["max_overlap"] <= 1 or sel["episode_ending_cap"] < 0:
        raise ConfigError("selection needs per_episode >= 1, 0 < max_overlap <= 1, episode_ending_cap >= 0")
    return config


def load_config(path: Optional[str | Path] = None) -> dict:
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        config = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read config {target.name}: {exc}") from exc
    return check_config(config)

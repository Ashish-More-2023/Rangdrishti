"""Step 3: six features, each a value in [0, 1] with plain-language reasons.

Evidence comes in two tiers:
  structural  timing and screenplay fields: when speech starts, delivery tags the
              writer gave a line, punctuation, what happens right after the cut,
              scene and episode boundaries, how fast shots change
  keyword     generic drama words in camera/action/sound text ("slams", "ominous").
              Always a capped bonus (config keyword_bonus_max), never the main signal.

Delivery tags ("Shouting, Furious") count as structural: they are a field the
screenwriter filled in for that line, not words we search for in free text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from engine.screenplay.show_index import IndexedBlock, IndexedEpisode, IndexedScene

from .windows import Window

QUESTION_AT_END = re.compile(r"\?[\s\"'”’)\]]*$")
FIRST_WORD = re.compile(r"[A-Za-z']+")


@dataclass(frozen=True)
class FeatureResult:
    name: str
    value: float                      # 0..1
    reasons: tuple[str, ...]
    evidence: tuple[str, ...] = ()    # block IDs that triggered the feature
    keyword_bonus: float = 0.0        # part of value that came from keywords (already included)


@dataclass(frozen=True)
class WindowContext:
    episode: IndexedEpisode
    window: Window
    blocks: tuple[IndexedBlock, ...]          # every block overlapping the window, timeline order
    scenes: tuple[IndexedScene, ...]          # scenes overlapping the window
    prev_line: Optional[IndexedBlock]         # last dialogue line ending at or before the window start
    next_line: Optional[IndexedBlock]         # first dialogue line starting at or after the window end
    tol: float

    @property
    def start(self) -> float:
        return self.window.start.t

    @property
    def end(self) -> float:
        return self.window.end.t

    @property
    def lines(self) -> list[IndexedBlock]:
        return [b for b in self.blocks if b.kind == "dialogue"]


class Vocabulary:
    """Compiled whole-word matchers for the config's generic vocabulary lists."""

    def __init__(self, vocabulary: dict[str, list[str]]):
        self._patterns = {
            name: [(cue, re.compile(rf"(?<![a-z]){re.escape(cue.lower())}(?![a-z])")) for cue in cues]
            for name, cues in vocabulary.items()
        }
        self.intense_words = frozenset(w.lower() for w in vocabulary.get("intense_delivery", []))
        self.openers = frozenset(w.lower() for w in vocabulary.get("dangling_openers", []))
        # A block appears in hundreds of overlapping windows; match its text once, then reuse.
        self._cache: dict[tuple[str, str], list[str]] = {}

    def find(self, list_name: str, text: str) -> list[str]:
        key = (list_name, text)
        if key not in self._cache:
            lowered = text.lower()
            self._cache[key] = [cue for cue, pattern in self._patterns.get(list_name, []) if pattern.search(lowered)]
        return self._cache[key]

    def intense(self, delivery: Optional[str]) -> list[str]:
        if not delivery:
            return []
        key = ("__delivery__", delivery)
        if key not in self._cache:
            self._cache[key] = sorted({w for w in re.findall(r"[a-z]+", delivery.lower()) if w in self.intense_words})
        return self._cache[key]


def clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 4)


def _keyword_bonus(hits: list[str], per_hit: float, cap: float) -> float:
    return round(min(cap, per_hit * len(set(hits))), 4)


# ---------------------------------------------------------------- hook (first seconds)
def hook(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    c = cfg["hook"]
    zone_end = ctx.start + c["window_s"]
    opening = [b for b in ctx.blocks if b.start_s < zone_end - ctx.tol]
    first_lines = [b for b in opening if b.kind == "dialogue" and b.start_s >= ctx.start - ctx.tol]
    value, reasons, evidence = 0.0, [], []

    if first_lines:
        line = first_lines[0]
        evidence.append(line.id)
        onset = line.start_s - ctx.start
        if line.voice == "V.O.":
            value += c["speech_onset"] * c["voice_over_factor"]
            reasons.append(f"voice-over starts {onset:.1f}s in (counts half)")
        else:
            value += c["speech_onset"]
            reasons.append(f"{line.speaker} speaks {onset:.1f}s in")
        if vocab.intense(line.delivery):
            value += c["intense_delivery"]
            reasons.append(f"first line is delivered {line.delivery!r}")
        if "!" in line.text or "?" in line.text:
            value += c["emphatic_punctuation"]
            reasons.append("first line is an exclamation or question")
    else:
        reasons.append(f"no speech in the first {c['window_s']:.0f}s")

    starts = [b for b in opening if b.start_s >= ctx.start - ctx.tol]
    if len(starts) >= c["fast_cutting_min_blocks"]:
        value += c["fast_cutting"]
        reasons.append(f"{len(starts)} beats in the first {c['window_s']:.0f}s (fast cutting)")

    hits = []
    for b in opening:
        if b.kind != "dialogue":
            hits += vocab.find("hook_cues", b.text) + (vocab.find("close_up_cues", b.text) if b.kind == "camera" else [])
    bonus = _keyword_bonus(hits, c["keyword_per_hit"], cfg["keyword_bonus_max"])
    if bonus:
        reasons.append(f"keyword bonus +{bonus:.2f} ({', '.join(sorted(set(hits)))})")
    return FeatureResult("hook", clamp(value + bonus), tuple(reasons), tuple(evidence), bonus)


# ---------------------------------------------------------------- cliffhanger (last seconds)
def cliffhanger(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    c = cfg["cliffhanger"]
    zone_start = ctx.end - c["window_s"]
    value, reasons, evidence = 0.0, [], []

    lines = ctx.lines
    last = max(lines, key=lambda b: (b.end_s, b.start_s, b.id)) if lines else None
    if last is not None and last.end_s >= zone_start - ctx.tol:
        evidence.append(last.id)
        if QUESTION_AT_END.search(last.text.strip()):
            value += c["ends_on_question"]
            reasons.append(f"ends on a question from {last.speaker}")
        if vocab.intense(last.delivery):
            value += c["intense_last_line"]
            reasons.append(f"last line is delivered {last.delivery!r}")
    else:
        reasons.append(f"no line lands in the last {c['window_s']:.0f}s")

    nxt = ctx.next_line
    if nxt is not None and nxt.start_s - ctx.end <= c["reply_gap_s"] + ctx.tol:
        value += c["cuts_before_reply"]
        evidence.append(nxt.id)
        reasons.append(f"cuts {max(0.0, nxt.start_s - ctx.end):.1f}s before {nxt.speaker} answers (unresolved)")

    ending_zone = cfg["selection"]["ending_zone_s"]
    if ctx.episode.duration_s is not None and ctx.episode.duration_s - ctx.end <= ending_zone + ctx.tol:
        value += c["episode_end"]
        reasons.append("ends at the episode's own ending")
    elif any(s.end_s is not None and abs(s.end_s - ctx.end) <= ctx.tol for s in ctx.scenes):
        value += c["scene_end"]
        reasons.append("ends where a scene ends")

    hits = []
    for b in ctx.blocks:
        if b.kind != "dialogue" and b.end_s > zone_start + ctx.tol:
            hits += vocab.find("cliffhanger_cues", b.text)
    bonus = _keyword_bonus(hits, c["keyword_per_hit"], cfg["keyword_bonus_max"])
    if bonus:
        reasons.append(f"keyword bonus +{bonus:.2f} ({', '.join(sorted(set(hits)))})")
    if not reasons:
        reasons.append("nothing left unresolved at the cut")
    return FeatureResult("cliffhanger", clamp(value + bonus), tuple(reasons), tuple(evidence), bonus)


# ---------------------------------------------------------------- dialogue density
def speech_coverage(ctx: WindowContext) -> float:
    """Share of the window during which someone is speaking (overlapping lines merged)."""
    spans = sorted((max(b.start_s, ctx.start), min(b.end_s, ctx.end)) for b in ctx.lines)
    covered, cur_start, cur_end = 0.0, None, None
    for s, e in spans:
        if cur_end is None or s > cur_end:
            if cur_end is not None:
                covered += cur_end - cur_start
            cur_start, cur_end = s, e
        else:
            cur_end = max(cur_end, e)
    if cur_end is not None:
        covered += cur_end - cur_start
    return covered / ctx.window.duration_s


def dialogue_density(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    c = cfg["dialogue_density"]
    share = speech_coverage(ctx)
    if share < c["zero_below"]:
        value = 0.0
    elif share < c["ideal_min"]:
        value = (share - c["zero_below"]) / (c["ideal_min"] - c["zero_below"])
    elif share <= c["ideal_max"]:
        value = 1.0
    else:
        value = 1.0 - (1.0 - c["value_at_full"]) * (share - c["ideal_max"]) / (1.0 - c["ideal_max"])
    return FeatureResult("dialogue_density", clamp(value), (f"speech covers {share:.0%} of the clip",))


# ---------------------------------------------------------------- intensity
def intensity(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    c = cfg["intensity"]
    minutes = ctx.window.duration_s / 60
    intense_lines = [b for b in ctx.lines if vocab.intense(b.delivery) or "!" in b.text]
    sounds = [b for b in ctx.blocks if b.kind == "sound" and b.start_s >= ctx.start - ctx.tol]
    structural = min(1.0, (len(intense_lines) + len(sounds)) / minutes / c["saturation_events_per_min"])

    cue_blocks = [b for b in ctx.blocks if b.kind != "dialogue"
                  and (vocab.find("hook_cues", b.text) or vocab.find("cliffhanger_cues", b.text))]
    bonus = round(min(cfg["keyword_bonus_max"],
                      len(cue_blocks) * c["keyword_event_weight"] / minutes / c["saturation_events_per_min"]), 4)
    reasons = [f"{len(intense_lines)} intense lines and {len(sounds)} sound cues in {ctx.window.duration_s:.0f}s"]
    if bonus:
        reasons.append(f"keyword bonus +{bonus:.2f} ({len(cue_blocks)} action/sound blocks with drama words)")
    return FeatureResult("intensity", clamp(structural + bonus), tuple(reasons), tuple(b.id for b in intense_lines), bonus)


# ---------------------------------------------------------------- standalone (proxy)
def standalone(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    """Cheap signs that a stranger could follow the clip. Only a proxy: the AI judges this properly later."""
    c = cfg["standalone"]
    value, reasons = 1.0, []
    lines = ctx.lines

    speakers = sorted({b.speaker for b in lines if b.speaker})
    extra = max(0, len(speakers) - c["max_easy_speakers"])
    if extra:
        value -= c["per_extra_speaker"] * extra
        reasons.append(f"{len(speakers)} speakers to keep track of")

    if lines and (word := FIRST_WORD.search(lines[0].text)) and word.group(0).lower() in vocab.openers:
        value -= c["dangling_opener"]
        reasons.append(f"opening line starts with {word.group(0)!r}, which points to earlier context")

    prev = ctx.prev_line
    if prev is not None and ctx.start - prev.end_s <= c["mid_conversation_gap_s"] + ctx.tol:
        value -= c["mid_conversation"]
        reasons.append(f"starts {max(0.0, ctx.start - prev.end_s):.1f}s after {prev.speaker} speaks (joins a conversation)")

    talk = sum(b.end_s - b.start_s for b in lines)
    vo = sum(b.end_s - b.start_s for b in lines if b.voice == "V.O.")
    if talk and vo / talk > c["voice_over_heavy_share"]:
        value -= c["voice_over_heavy"]
        reasons.append(f"{vo / talk:.0%} of speech is voice-over")

    if any(s.start_s is not None and abs(s.start_s - ctx.start) <= ctx.tol for s in ctx.scenes):
        value += c["scene_start_bonus"]
        reasons.append("starts where a scene starts")
    if not reasons:
        reasons.append("no standalone warning signs")
    return FeatureResult("standalone", clamp(value), tuple(reasons))


# ---------------------------------------------------------------- duration fit
def duration_fit(ctx: WindowContext, cfg: dict, vocab: Vocabulary) -> FeatureResult:
    c, w = cfg["duration_fit"], cfg["window"]
    d = ctx.window.duration_s
    lo, hi, edge = c["ideal_min_s"], c["ideal_max_s"], c["edge_value"]
    if lo <= d <= hi:
        value = 1.0
    elif d < lo:
        value = edge + (1 - edge) * (d - w["min_duration_s"]) / (lo - w["min_duration_s"])
    else:
        value = 1.0 - (1 - edge) * (d - hi) / (w["max_duration_s"] - hi)
    return FeatureResult("duration_fit", clamp(value), (f"{d:.1f}s (ideal {lo:.0f}-{hi:.0f}s)",))


FEATURES = {
    "hook": hook,
    "cliffhanger": cliffhanger,
    "dialogue_density": dialogue_density,
    "intensity": intensity,
    "standalone": standalone,
    "duration_fit": duration_fit,
}

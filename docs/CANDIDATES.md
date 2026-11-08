# Promo candidates (Stage 2)

Deterministic, rule-based shortlist of promo clips. No AI. Reads `show.json` (Stage 1) and writes `candidates.json`, `candidates_report.json` and `candidates_review.md` next to it.

## Pipeline

```
timeline.py   clean cut points        every block boundary; rejected if it splits a dialogue or camera block
windows.py    candidate windows       every pair of clean cuts 20-60 s apart, inside one episode
features.py   six features            each 0-1 with reasons; structure first, keywords a capped bonus
scoring.py    score                   sum(weight x feature) - scene-crossing penalty
select.py     per-episode shortlist   greedy by score; overlap rule, ending cap, minimum score
render.py     outputs                 candidate records and the human review file
pipeline.py   orchestration           also validates EVERY window with engine/validation/promo_rules.py
```

## Why cuts can only fall on clean boundaries

A clip that starts mid-sentence or mid-shot looks broken. So a cut at time t is allowed only if no dialogue block and no camera block runs across t. Action and sound blocks may be trimmed (flagged `trims_action_or_sound`), because they describe what happens on screen rather than a unit the viewer perceives as cut.

## Features

| Feature | Weight | Structural evidence (main) | Keyword bonus (capped at 0.15) |
|---|---|---|---|
| Hook (first 3 s) | 0.30 | speech starts (voice-over counts half), intense delivery tag, `!`/`?` in first line, 3+ beats starting (fast cutting) | drama verbs, close-up/zoom words in camera/action/sound text |
| Cliffhanger (last 4 s) | 0.30 | last line is a question, last line intense, the next line starts within 1.5 s after the cut (unresolved), episode ending, scene ending | cliffhanger words (ominous, sting, freezes...) |
| Dialogue density | 0.10 | share of the clip with speech; ideal 45-85% | none |
| Intensity | 0.10 | intense or exclaimed lines plus sound cues, per minute | action/sound blocks with drama words |
| Standalone (proxy) | 0.10 | penalties: more than 3 speakers, opening line starting "He/She/That/And...", starting within 1.5 s of a previous line, voice-over-heavy; bonus: starts at a scene start | none |
| Duration fit | 0.10 | 1.0 at 30-45 s, 0.5 at 20 s and 60 s | none |

Delivery tags ("Shouting, Furious") are treated as structural: they are a field the screenwriter set for that line, not words searched for in free text. Crossing a scene boundary costs 0.05 per crossing (max 0.15) and is flagged, never rejected.

## Selection

Highest score first. A window is skipped if it is below `min_score` (0.30), overlaps an already chosen clip by more than 50% of the shorter clip, or ends within 3 s of the episode's end when the per-episode ending cap (1) is used up. Up to 6 per episode: a target, not a quota. Short episodes physically cannot hold six distinct clips.

## Validation

`engine/validation/promo_rules.py` checks duration, clean cuts, timestamps, episode isolation and block/scene references. It re-implements the clean-cut check on purpose, so it independently cross-checks the generator. Stage 3 (AI) and Stage 4 (multi-segment) will reuse it; multi-segment promos are enabled with `RuleConfig(max_segments=..., single_episode=False)`.

## Configuration

`engine/candidates/candidates_config.json` holds every weight, threshold and word list, with a `config_version`. Its SHA-256 is stamped on every output. Vocabulary must stay generic drama language, so the same config works on a new show. The starting weights are reasoned priors; change them only against a human gold set.

## Gold set

`python -m engine.evaluation.worksheet <show folder>` writes a neutral worksheet (`data/config/gold_worksheet.md`, built from show.json only) and a blank `data/config/gold_promos.json` (same schema as `docs/gold_promos.template.json`; never overwritten once it exists). A person adds 10-15 picks made before reading the candidates. The report then gives recall (gold clips at least half covered by a candidate), hook alignment, and the same recall for random valid windows with the same per-episode budget. If the rules do not beat random, they are not helping.

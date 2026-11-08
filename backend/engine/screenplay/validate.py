"""Semantic checks on parsed episodes. Every function only reports; nothing is changed.

error   - the data cannot be trusted as-is (later stages must not use it)
warning - suspicious but usable; a human should look
info    - worth knowing, no action needed
"""
from __future__ import annotations

from collections import Counter

from .models import Episode, Issue
from .parser import EPISODE_IN_FILENAME

TOLERANCE_S = 0.01  # timestamps carry two decimals; ignore float noise below this


def _issue(severity, code, message, episode: Episode, line=None) -> Issue:
    return Issue(severity, code, message, episode.source.file, line)


def check_scene_boundaries(episode: Episode) -> list[Issue]:
    issues = []
    for scene in episode.scenes:
        line = scene.source.marker_line
        if scene.source.start_raw is None or scene.source.end_raw is None:
            missing = [n for n, v in (("start", scene.source.start_raw), ("end", scene.source.end_raw)) if v is None]
            issues.append(_issue("error", "scene_missing_boundary", f"{scene.id} has no scene {' or '.join(missing)}", episode, line))
        elif scene.start_s is not None and scene.end_s is not None and scene.end_s <= scene.start_s:
            issues.append(_issue("error", "scene_nonpositive_duration", f"{scene.id} ends at or before it starts", episode, line))

    timed = [s for s in episode.scenes if s.start_s is not None and s.end_s is not None]
    if timed and timed[0].start_s > TOLERANCE_S:
        issues.append(_issue("info", "first_scene_not_at_zero", f"{timed[0].id} starts at {timed[0].start_s}s", episode, timed[0].source.marker_line))
    for prev, cur in zip(timed, timed[1:]):
        gap = round(cur.start_s - prev.end_s, 3)
        if gap > TOLERANCE_S:
            issues.append(_issue("warning", "scene_gap", f"{gap}s gap between {prev.id} and {cur.id}", episode, cur.source.marker_line))
        elif gap < -TOLERANCE_S:
            issues.append(_issue("warning", "scene_overlap", f"{-gap}s overlap between {prev.id} and {cur.id}", episode, cur.source.marker_line))
    return issues


def check_scene_numbering(episode: Episode) -> list[Issue]:
    numbers = [s.number for s in episode.scenes]
    issues = [
        _issue("error", "duplicate_scene_number", f"Scene {n} appears {c} times", episode)
        for n, c in sorted(Counter(numbers).items()) if c > 1
    ]
    if numbers and numbers != list(range(1, len(numbers) + 1)) and not issues:
        issues.append(_issue("warning", "scene_numbering", f"Scene numbers are {numbers}, expected 1..{len(numbers)}", episode))
    return issues


def check_blocks(episode: Episode) -> list[Issue]:
    issues = []
    for scene in episode.scenes:
        for block in scene.blocks:
            line = block.source.label_line
            if block.start_s is None or block.end_s is None:
                continue  # already reported by the parser as missing or invalid
            if block.end_s < block.start_s:
                issues.append(_issue("error", "block_negative_duration", f"{block.id} ends before it starts", episode, line))
            elif block.end_s == block.start_s:
                issues.append(_issue("warning", "block_zero_duration", f"{block.id} has zero duration", episode, line))
            if scene.start_s is not None and block.start_s < scene.start_s - TOLERANCE_S:
                issues.append(_issue("warning", "block_before_scene_start", f"{block.id} starts {round(scene.start_s - block.start_s, 3)}s before {scene.id}", episode, line))
            if scene.end_s is not None and block.end_s > scene.end_s + TOLERANCE_S:
                issues.append(_issue("warning", "block_after_scene_end", f"{block.id} ends {round(block.end_s - scene.end_s, 3)}s after {scene.id}", episode, line))
    return issues


def check_episode_number(episode: Episode) -> list[Issue]:
    match = EPISODE_IN_FILENAME.search(episode.source.file)
    if episode.number is not None and match and int(match.group(1)) != episode.number:
        return [_issue("warning", "episode_number_mismatch", f"Header says episode {episode.number}, file name says {int(match.group(1))}", episode)]
    return []


def check_show(episodes: list[Episode]) -> list[Issue]:
    issues = []
    numbers = Counter(e.number for e in episodes if e.number is not None)
    for number, count in sorted(numbers.items()):
        if count > 1:
            issues.append(Issue("error", "duplicate_episode_number", f"Episode {number} appears {count} times", "(show)"))
    if numbers:
        missing = sorted(set(range(min(numbers), max(numbers) + 1)) - set(numbers))
        if missing:
            issues.append(Issue("warning", "episode_numbering_gap", f"Missing episode numbers: {missing}", "(show)"))
    ids = Counter(
        identifier
        for e in episodes
        for identifier in [e.id, *(s.id for s in e.scenes), *(b.id for s in e.scenes for b in s.blocks)]
    )
    for identifier, count in sorted(ids.items()):
        if count > 1:
            issues.append(Issue("error", "duplicate_id", f"ID {identifier} is used {count} times", "(show)"))
    return issues


def validate_show(episodes: list[Episode]) -> list[Issue]:
    issues = []
    for episode in episodes:
        for check in (check_scene_boundaries, check_scene_numbering, check_blocks, check_episode_number):
            issues.extend(check(episode))
    issues.extend(check_show(episodes))
    return issues

"""Strict timestamp parsing. Invalid values return None; they are never guessed or repaired."""
import re
from typing import Optional

# MM:SS, MM:SS.f..fff, or H:MM:SS(.fff). Seconds must be 00-59.
_TIMESTAMP = re.compile(r"^(?:(\d+):)?(\d{1,3}):([0-5]\d)(?:\.(\d{1,3}))?$")


def parse_timestamp(raw: str) -> Optional[float]:
    match = _TIMESTAMP.match(raw.strip())
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    if hours is not None and int(minutes) > 59:
        return None
    total = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    if fraction:
        total += int(fraction) / 10 ** len(fraction)
    return round(total, 3)


def format_timestamp(seconds: Optional[float]) -> str:
    if seconds is None:
        return "??:??.??"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):02d}:{secs:05.2f}"

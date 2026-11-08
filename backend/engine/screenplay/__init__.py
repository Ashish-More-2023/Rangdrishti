"""Deterministic screenplay parser (no AI).

Pipeline, each step in its own module:
    sources    read a ZIP or directory into SourceFile objects (originals untouched)
    parser     line-by-line state machine: text -> Episode/Scene/Block + issues
    normalize  speaker names (title rule + manual aliases), derived durations
    validate   semantic checks; reports problems, never repairs them
    render     compact per-episode text with block IDs (what the AI will read)
    report     parse_report.json
    pipeline   wires the steps together and writes outputs
"""
from .pipeline import ParseResult, parse_show, write_outputs

SCHEMA_VERSION = "1.0.0"

__all__ = ["SCHEMA_VERSION", "ParseResult", "parse_show", "write_outputs"]

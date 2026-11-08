"""Compact per-episode text with one line per block, each starting with its block ID.
This is the form the AI will read in later stages. Timestamps are included so a
human can check a rendering against the source file."""
from .models import Episode
from .timestamps import format_timestamp as ts


def render_block_label(block) -> str:
    if block.kind == "dialogue":
        label = str(block.speaker)
        if block.voice:
            label += f" [{block.voice}]"
        return f"{label} ({block.delivery})" if block.delivery else label
    return block.kind.upper()


def render_episode(episode: Episode) -> str:
    lines = [f"{episode.id} | {episode.source.header.get('EPISODE NUMBER', 'Episode ?')} | {ts(episode.duration_s)}"]
    if episode.logline:
        lines.append(f"LOGLINE: {episode.logline}")
    for scene in episode.scenes:
        lines.append("")
        lines.append(f"[{scene.id}] {scene.heading or '(no heading)'} | {ts(scene.start_s)}-{ts(scene.end_s)}")
        for block in scene.blocks:
            text = block.text.replace("\n", " / ")
            lines.append(f"{block.id} {ts(block.start_s)}-{ts(block.end_s)} {render_block_label(block)}: {text}")
    return "\n".join(lines) + "\n"

"""Build small synthetic show.json documents for Stage 2 tests (no real screenplay content)."""
import copy

from engine.candidates import load_config
from engine.screenplay.timestamps import format_timestamp


def blk(kind, start, end, text="", speaker=None, delivery=None, voice=None):
    return {"kind": kind, "start_s": start, "end_s": end, "text": text, "speaker": speaker,
            "delivery": delivery, "voice": voice}


def line(start, end, text, speaker="ANA", delivery=None, voice=None):
    return blk("dialogue", start, end, text, speaker, delivery, voice)


def shots(start, end, every=5.0, text="Medium shot."):
    """Camera blocks tiling [start, end) every `every` seconds."""
    out, t = [], start
    while t < end - 1e-9:
        out.append(blk("camera", round(t, 2), round(min(end, t + every), 2), text))
        t += every
    return out


def episode(number, scenes, duration=None):
    """scenes: list of (start, end, [blocks]). Block IDs follow the parser's scheme."""
    ep_id = f"E{number:03d}"
    out_scenes = []
    for s_no, (s_start, s_end, blocks) in enumerate(scenes, start=1):
        scene_id = f"{ep_id}-S{s_no:02d}"
        out_blocks = []
        for b_no, b in enumerate(blocks, start=1):
            b = dict(b)
            b.update(id=f"{scene_id}-B{b_no:03d}", index=b_no, annotations=[],
                     source={"start_raw": format_timestamp(b["start_s"]) if b["start_s"] is not None else None,
                             "end_raw": format_timestamp(b["end_s"]) if b["end_s"] is not None else None})
            out_blocks.append(b)
        out_scenes.append({"id": scene_id, "number": s_no, "heading": f"INT. ROOM {s_no} - DAY",
                           "start_s": s_start, "end_s": s_end, "blocks": out_blocks})
    ends = [s[1] for s in scenes]
    return {"id": ep_id, "number": number, "duration_s": duration if duration is not None else max(ends),
            "scenes": out_scenes, "source": {"file": f"synthetic-ep-{number:03d}.txt"}}


def show(*episodes):
    return {"schema_version": "1.0.0", "parser_version": "1.0.0",
            "show": {"title": "Synthetic Show", "slug": "synthetic-show"}, "speakers": {},
            "episodes": list(episodes)}


def config(**overrides):
    """Default config with dotted overrides, e.g. config(**{"selection.per_episode": 2})."""
    cfg = copy.deepcopy(load_config())
    for dotted, value in overrides.items():
        target = cfg
        *path, last = dotted.split(".")
        for key in path:
            target = target[key]
        target[last] = value
    return cfg


def standard_episode(number=1):
    """90 s, one scene, shots every 5 s; lines sit inside shots except one crossing the 15 s cut."""
    blocks = shots(0, 90) + [
        line(0.3, 2.5, '"Where were you last night?"', "ANA", "Furious"),
        line(6.0, 9.0, '"Out."', "BEN"),
        line(12.0, 17.0, '"That is not an answer."', "ANA", "Cold"),     # crosses the 15 s shot boundary
        line(21.0, 24.0, '"Then hear this."', "BEN", "Defiant"),
        line(31.0, 34.0, '"You lied to me!"', "ANA", "Shouting"),
        line(41.0, 44.0, '"I had no choice."', "BEN"),
        line(51.0, 54.0, '"Who else knows?"', "ANA", "Desperate"),
        line(55.5, 58.0, '"Your sister."', "BEN", "Quiet"),
        line(66.0, 69.0, '"Get out."', "ANA"),
        line(76.0, 79.0, '"This is not over?"', "BEN", "Menacing"),
        blk("sound", 80.0, 81.0, "A door slams."),
        blk("action", 13.0, 22.0, "Ana paces across the room."),             # action may be trimmed
    ]
    return episode(number, [(0.0, 90.0, blocks)])

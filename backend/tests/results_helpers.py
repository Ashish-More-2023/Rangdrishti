"""Write a complete synthetic processed folder (show, candidates, mock-judged promos)."""
import json
from pathlib import Path

from engine.ai import MockProvider
from engine.candidates import find_candidates, load_config
from engine.candidates import write_outputs as write_candidates
from engine.judge import judge_show, load_judge_config
from engine.judge import write_outputs as write_promos

from .candidate_helpers import show, standard_episode

SLUG = "synthetic-show"


def build_processed(data_dir: Path, judged: bool = True) -> Path:
    folder = data_dir / "processed" / SLUG
    folder.mkdir(parents=True, exist_ok=True)
    doc = show(standard_episode(1), standard_episode(2))
    (folder / "show.json").write_text(json.dumps(doc), encoding="utf-8")
    cands = find_candidates(doc, load_config())
    write_candidates(cands, folder)
    if judged:
        write_promos(judge_show(doc, cands.candidates, MockProvider(), load_judge_config(), data_dir / "raw"), folder)
    return folder

# Screenplay parser (Stage 1)

Turns a screenplay pack (folder or ZIP of episode `.txt` files) into one validated dataset. It is deterministic Python with no AI: the same input always gives byte-identical output.

## Pipeline

```
sources.py    read folder or ZIP in memory; originals are never modified or extracted
parser.py     state machine: text -> Episode / Scene / Block, plus syntax issues
normalize.py  canonical speaker names, episode durations
validate.py   meaning-level checks; reports problems, never changes data
render.py     compact per-episode text with block IDs
report.py     parse_report.json
pipeline.py   runs the steps and writes the outputs
```

Parsing, normalisation and validation are separate, so each can be tested alone and a new rule never hides inside the parser.

## The state machine

```
HEADER ──"--- SCRIPT START ---"──▶ PRE_SCENE ──"SCENE 01"──▶ SCENE_META ──"Actions and dialogue:"──▶ BODY
                                                                  ▲                                   │
                                                                  └────────────"SCENE 02"─────────────┘
BODY ──"--- SCRIPT END ---"──▶ AFTER_END
```

In BODY, `**LABEL:**` opens a block, the next `Start: (..) | End: (..)` line times it, and the lines after it are its text. The block closes at the next label, scene marker or script end.

Three rules make it trustworthy:

1. **Every non-blank line gets exactly one category** (`header_field`, `scene_meta`, `block_label`, `block_timing`, `block_text`, ...). A line that fits no rule for the current state becomes `unaccounted`, is listed in the report with its text and line number, and raises an error. Nothing is dropped silently. The category counts must add up to the file's non-blank lines, and the tests check this.
2. **Patterns are case-insensitive**, because packs differ (episode 6 of the sample pack writes `SCENE START:`).
3. **It is tolerant but loud.** A missing `SCRIPT START` or `Actions and dialogue:` line is a warning and parsing continues. A missing or invalid timestamp is an error and the value stays `null`.

## Data model

`Show → Episode → Scene → Block`. Each object has normalised fields at the top and a separate `source` object holding exactly what the file said: raw label, raw timestamp strings and line numbers.

Block IDs such as `E001-S01-B008` are built from the screenplay's own episode number, scene number and the block's position in its scene. They stay stable across runs and do not shift when other episodes are added. Later stages will make the AI cite these IDs, and code will map them back to exact timestamps.

## Label parsing

| Label | kind | speaker | voice | delivery | annotations |
|---|---|---|---|---|---|
| `CAMERA` | camera | | | | |
| `HOUSEKEEPER (Cold, Commanding)` | dialogue | HOUSEKEEPER | | Cold, Commanding | |
| `MARA (V.O.) (Reflective)` | dialogue | MARA | V.O. | Reflective | |
| `LORD WREN (O.S. / Continues)` | dialogue | LORD WREN | O.S. | | continues |
| `HARBOR MASTER (Edmund) (Decisive)` | dialogue | HARBOR MASTER | | Decisive | Edmund |

`voice` matters for promos: a voice-over line is not someone speaking on screen.

## Speaker normalisation

1. A manual alias from `speaker_aliases.json` always wins.
2. Title rule: `LADY MARA` becomes `MARA` only if `MARA` also speaks in the show.
3. Otherwise the name stays as written, upper-cased and with spacing cleaned up.

Titles alone (`LORD`) and descriptions (`THE STRANGER`) are never merged with names, because that needs story knowledge. Merging two different characters would silently break the later "makes sense on its own" check, so it is left to a human via aliases. Identity notes like `(Edmund)` are reported as alias suggestions.

## Validation codes

| Severity | Codes |
|---|---|
| error | `unrecognized_line`, `invalid_timestamp`, `malformed_timing_line`, `block_missing_timing`, `text_before_timing`, `scene_missing_boundary`, `scene_nonpositive_duration`, `block_negative_duration`, `duplicate_scene_number`, `duplicate_episode_number`, `duplicate_id`, `episode_number_missing`, `no_script_body`, `no_scenes`, `unreadable_file`, `no_screenplay_files`, `aliases_invalid`, `aliases_unreadable` |
| warning | `missing_script_start`, `missing_section_marker`, `unexpected_script_start`, `scene_gap`, `scene_overlap`, `scene_numbering`, `block_before_scene_start`, `block_after_scene_end`, `block_zero_duration`, `empty_block_text`, `unusual_label`, `episode_number_from_filename`, `episode_number_mismatch`, `episode_numbering_gap` |
| info | `first_scene_not_at_zero`, `unknown_header_field`, `speaker_annotation`, `unused_alias` |

## Outputs

Written to `data/processed/<show-slug>/` (ignored by Git):

- `show.json`: schema-versioned dataset
- `parse_report.json`: counts, line accounting, issues, speaker merges, per-episode token estimates
- `episodes/E001.txt` …: one line per block, `E001-S01-B003 00:04.00-00:07.50 MARA (Breathless): "..."` (from the synthetic test fixture)

`schema_version` changes when the JSON shape changes; `parser_version` changes when parsing behaviour changes.

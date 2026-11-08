# AI judge (Stage 3)

The rules shortlist about 230 candidates; an AI model judges them; code validates and ranks.

## Flow

```
show.json + candidates.json
  -> one prompt per episode: every block as "ID start-end LABEL: text", plus that episode's candidates
  -> model returns JSON: hook/cliffhanger/standalone scores (0-10), verdict, one-line hook, cliffhanger, why,
     and optionally a tighter start/end given as a block ID
  -> raw response saved verbatim in data/raw_outputs/<slug>/<provider-model>/ (also the cache)
  -> strict parse: malformed items are reported, never repaired; missing ones fall back to the rule score
  -> trims applied only if they pass engine/validation/promo_rules.py and keep >= 50% of the original clip
  -> final_score = 0.3 x rule score + 0.7 x AI score (AI = 0.4 hook + 0.2 standalone + 0.4 cliffhanger, /10)
  -> promos.json, promos.csv, judge_report.json; "post first" = top 10, max 1 per episode, no "skip"
```

## Why it is built this way

| Decision | Reason |
|---|---|
| The model answers with block IDs, never timestamps | Models invent plausible times; code maps IDs to exact times and validates them. |
| One call per episode (about 50 for a show) | Fits free-tier limits; the model sees full episode context for the standalone judgement. |
| Raw responses saved before parsing, and reused as a cache | Separates raw AI output from processed results; re-runs are free and reproducible. |
| Provider chosen by environment variables | Swap Gemini for Groq, OpenRouter, Ollama or a stronger model without code changes. |
| Mock provider | Tests and offline demos; its scores are placeholders and every output says so. |
| Rule score kept in the final score (30%) | The AI can override the rules but not ignore structure entirely; both are visible per promo. |

## Running

```powershell
python manage.py judge_promos --provider gemini --list-models          # pick a Flash model, put it in .env as LLM_MODEL
python manage.py judge_promos "..\data\processed\<show-slug>" --episodes E001,E002   # cheap trial
python manage.py judge_promos "..\data\processed\<show-slug>"                        # full show (~50 calls, ~6 min)
```

Options: `--max-calls N` (respect a daily quota; cached episodes stay free), `--refresh` (call again), `--provider mock`.

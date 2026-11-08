# Rangdrishti

Finds the best 20-60 second promo clips in timestamped microdrama screenplays, with exact start and end times, a hook, a cliffhanger and a reason for each. Built for the Kuku AI Generalist Assignment (Problem 1: Find the Promos).

**The core idea: the AI judges, code measures.** Language models invent plausible timestamps, so the model never produces a time. Every line of the screenplay gets a stable ID; rules shortlist clips that start and end cleanly; the AI judges the shortlist by ID; code turns IDs into exact times and validates every clip.

Exact setup and run steps: **[docs/RUNBOOK.md](docs/RUNBOOK.md)**.

## How it works

| Stage | Command | What it does | AI? |
|---|---|---|---|
| 1. Parse | `parse_show` | Reads a folder or ZIP of episode `.txt` files into `show.json`: episodes, scenes and timed blocks with IDs like `E001-S01-B008`. Every line is accounted for; nothing is silently dropped or repaired. | No |
| 2. Shortlist | `find_candidates` | Finds every clip between clean cuts (never inside a spoken line or a camera shot) lasting 20-60 s, scores it on six explainable features and keeps up to 6 diverse candidates per episode. | No |
| 3. Judge | `judge_promos` | One AI call per episode returns hook, cliffhanger and standalone scores, a verdict (post / maybe / skip) and one-line reasons. Code validates, ranks and exports. | Yes |
| 4. Review | web page | Post-first picks, full table with filters, the script inside each clip, CSV download. | Human |

Results on the 50-episode input pack: 100 scenes and 3,727 timed blocks parsed with 0 errors; 16,837 valid windows shortlisted to 230 candidates in about 2 s; 0 clips break a hard rule; output is identical across runs.

## Quick start (Windows PowerShell)

```powershell
cd <repo>
py -3 -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env                      # set LLM_PROVIDER, LLM_MODEL, LLM_API_KEY (see RUNBOOK)
Expand-Archive "<input-pack>.zip" -DestinationPath data\input
cd backend
python manage.py migrate
python manage.py parse_show ..\data\input
python manage.py find_candidates "..\data\processed\<show-slug>"
python manage.py judge_promos "..\data\processed\<show-slug>"
python manage.py runserver 127.0.0.1:8000        # second terminal: cd frontend; npm install; npm run dev
```

`<show-slug>` is the folder name `parse_show` prints on its last line. Without an API key, add `--provider mock` to `judge_promos`: the whole pipeline runs with clearly marked placeholder scores.

## Input format

A pack is a folder (or ZIP) with one UTF-8 `.txt` file per episode. This is the start of the fictional test episode in `backend/tests/fixtures/screenplays/clean/The Lighthouse Heir/` (the real pack is confidential and never in this repo):

```
EPISODE NUMBER: Episode 1
EPISODE LOGLINE: Mara inherits a cliffside lighthouse and finds a stranger already living in it.
CONTINUITY NOTES: First episode. Establishes Mara and Tobias.

--- SCRIPT START ---

SCENE 01
Scene heading: EXT. CLIFF LIGHTHOUSE – DUSK
Scene start: 00:00.00
Scene end: 00:20.00

Actions and dialogue:

**CAMERA:**
Start: (00:00.00) | End: (00:04.00)
Wide shot of a lighthouse on a cliff as waves crash below.

**LADY MARA (Breathless):**
Start: (00:04.00) | End: (00:07.50)
"It's mine now.
All of it."

**MARA (V.O.) (Quiet, Certain):**
Start: (00:09.00) | End: (00:12.00)
"I knew his voice before I saw his face."
```

The parser also accepts upper-case scene headers (`SCENE START:`), labels with several parentheticals (`(V.O.)`, `(O.S. / Continues)`, `(Edmund) (Gruff)`), wrapped dialogue lines, CRLF line endings and a missing `SCRIPT START` marker (reported as a warning). Anything it cannot read is listed in `parse_report.json` with its line number.

To try the whole pipeline on this fictional show:

```powershell
cd backend
python manage.py parse_show "tests\fixtures\screenplays\clean\The Lighthouse Heir"
python manage.py find_candidates "..\data\processed\the-lighthouse-heir"
python manage.py judge_promos "..\data\processed\the-lighthouse-heir" --provider mock
```

## Output examples (from that fictional show)

**Episode rendering** (`episodes/E001.txt`): one line per block, the form the AI reads:

```
[E001-S01] EXT. CLIFF LIGHTHOUSE – DUSK | 00:00.00-00:20.00
E001-S01-B001 00:00.00-00:04.00 CAMERA: Wide shot of a lighthouse on a cliff as waves crash below.
E001-S01-B003 00:04.00-00:07.50 MARA (Breathless): "It's mine now. / All of it."
```

**Candidate** (`candidates.json`, abridged): exact times, the boundary blocks and a score that explains itself:

```
id E001-W00400-02600   00:04.00-00:26.00   22.0 s   score 0.436
hook: "MARA speaks 0.0s in"     cliffhanger: "last line is delivered 'Defiant'"
```

**Final ranking** (`promos.csv`, opens in Excel). With `--provider mock` the AI columns are placeholders, as shown:

```
rank,post_first_rank,promo_id,episode_id,start,end,duration_s,final_score,rule_score,ai_score,verdict,hook,cliffhanger,why,trimmed,judged
1,1,E001-W00400-02600,E001,00:04.00,00:26.00,22.0,0.4949,0.4364,0.52,maybe,[mock] opening moment,[mock] unresolved ending,"[mock] placeholder judgement, not a real assessment",,yes
```

## Output files

All outputs are written under `data/`, which Git ignores.

| File | Stage |
|---|---|
| `data/processed/<show-slug>/show.json`, `parse_report.json`, `episodes/E0NN.txt` | 1 |
| `candidates.json`, `candidates_report.json`, `candidates_review.md` | 2 |
| `promos.json`, `promos.csv`, `judge_report.json` | 3 |
| `data/raw_outputs/<show-slug>/<provider-model>/E0NN-<hash>.json` | 3: the exact prompt and the model's reply, saved before parsing (also the cache) |

## Repository layout

```
backend/
  config/            Django settings and URLs
  api/               thin HTTP layer and management commands (parse_show, find_candidates, judge_promos)
  engine/            all logic, plain Python with no Django imports
    screenplay/      parser, normaliser, validator, show.json index
    candidates/      rule-based shortlist and its versioned config (candidates_config.json)
    judge/           AI prompt, strict answer parsing, final ranking, exports (judge_config.json)
    ai/              swappable providers: Gemini / any OpenAI-compatible API, offline mock
    validation/      hard rules every promo must pass
    evaluation/      gold-set recall against a random baseline, annotation worksheet
    results/         read-only access for the web page
  tests/             unit tests with synthetic fixtures; real-pack tests skip when the pack is absent
frontend/            React + Vite + Tailwind results page
data/                local only, ignored by Git: input/, processed/, raw_outputs/, config/
docs/                RUNBOOK, ARCHITECTURE, PARSER, CANDIDATES, JUDGE, BACKLOG
```

## API (read-only)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health/` | Backend and database status |
| GET | `/api/shows/` | Processed shows and whether they have ranked promos |
| GET | `/api/shows/<slug>/promos/` | Ranked promos, post-first list, run details (model, mock flag) |
| GET | `/api/shows/<slug>/promos/<promo_id>/` | One promo with the screenplay lines inside it |
| GET | `/api/shows/<slug>/promos.csv` | CSV download |

Every response uses `{"status": "ok", "data": ...}` or `{"status": "error", "error": {"code", "message"}}`.

## Changing the model

Edit `.env`; no code changes. `LLM_PROVIDER=gemini` uses Google's OpenAI-compatible endpoint; `LLM_PROVIDER=openai_compatible` with `LLM_BASE_URL` works with Groq, OpenRouter or a local Ollama server; `LLM_PROVIDER=mock` runs offline. `python manage.py judge_promos --list-models` shows what a key can use.

## Confidential data

The Kuku input pack and everything derived from it stay in `data/`, which Git ignores apart from empty `.gitkeep` markers. Tests use fictional fixtures. Never commit `.env`. Before pushing, run `git status` and check that no `data\` files, `.env`, `db.sqlite3`, `.zip` or `episode-*.txt` files are listed.

## Further reading

- [docs/RUNBOOK.md](docs/RUNBOOK.md): exact steps, troubleshooting, packaging raw outputs
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): decisions and reasons
- [docs/PARSER.md](docs/PARSER.md), [docs/CANDIDATES.md](docs/CANDIDATES.md), [docs/JUDGE.md](docs/JUDGE.md): how each stage works
- [docs/BACKLOG.md](docs/BACKLOG.md): known weaknesses and deferred work

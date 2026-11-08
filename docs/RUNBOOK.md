# Runbook: run Rangdrishti from scratch (Windows PowerShell)

Every command below is meant to be copied as is. Replace `<repo>` with your project folder (for example `D:\kuku\rangdrishti-stage4\rangdrishti`) and `<show-slug>` with the folder name `parse_show` prints on its `Output:` line.

## 0. Prerequisites (once per computer)

```powershell
py --version      # Python 3.10 to 3.13
node --version    # v20.19+ or v22.12+
git --version
```

Missing one? `winget install Python.Python.3.12`, `winget install OpenJS.NodeJS.LTS`, `winget install Git.Git`, then reopen PowerShell.

## 1. Python environment (once per copy of the project)

```powershell
cd <repo>
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt
```

If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. Your prompt should start with `(venv)`.

## 2. Settings file

```powershell
Copy-Item .env.example .env
notepad .env
```

Each setting must appear exactly once. Edit the existing lines rather than adding new ones:

```
LLM_PROVIDER=gemini
LLM_MODEL=
LLM_API_KEY=<your key from Google AI Studio>
LLM_MIN_INTERVAL_S=6.5
```

Never paste `.env` or the key into chats, screenshots or Git. To check settings safely:

```powershell
Get-Content .env | Select-String "LLM_" | Select-String -NotMatch "API_KEY"
```

## 3. Input data

```powershell
Expand-Archive "<path>\<input-pack>.zip" -DestinationPath data\input
```

Or copy it from an earlier copy of the project (also copies cached AI answers, so they are not paid for twice):

```powershell
$old = "<old repo>\data"
Copy-Item "$old\input\*" data\input\ -Recurse -Force
Copy-Item "$old\raw_outputs\*" data\raw_outputs\ -Recurse -Force -ErrorAction SilentlyContinue
```

Files in `data\input` are read only, never modified.

## 4. Database and tests

```powershell
cd backend
python manage.py migrate
pytest -v
```

Expect every test to pass (about 170). Tests marked "real pack" run only when the pack is in `data\input`.

## 5. Choose the AI model (once)

```powershell
python manage.py judge_promos --list-models
```

Pick a Flash model from the list and write it **without** the `models/` prefix in `.env`, for example `LLM_MODEL=gemini-3.8-flash`. If it later fails with HTTP 429 or 403, it is probably not in your free quota: use `LLM_MODEL=gemini-2.5-flash`.

## 6. Run the pipeline (from `backend`, venv active)

```powershell
python manage.py parse_show ..\data\input
python manage.py find_candidates "..\data\processed\<show-slug>"
python manage.py judge_promos "..\data\processed\<show-slug>" --episodes E001,E002
python manage.py judge_promos "..\data\processed\<show-slug>"
```

| Command | Expect on the sample pack |
|---|---|
| `parse_show` | 50 episodes, 100 scenes, 3727 blocks, 0 unaccounted, 0 errors |
| `find_candidates` | 16837 valid windows, 230 candidates, `0 of 16837 windows fail` |
| `judge_promos` (trial) | `gemini / <model>`, no MOCK warning, `live: 2` |
| `judge_promos` (full) | About 50 calls, `0 of 230 promos fail hard rules` |

Useful options for `judge_promos`:

| Option | Use |
|---|---|
| `--episodes E001,E002` | Judge only these episodes |
| `--max-calls 10` | At most 10 new API calls (daily quota); cached episodes stay free |
| `--max-calls 0` | No API calls: rebuild `promos.json` from every cached answer |
| `--refresh` | Ignore the cache and ask the model again |
| `--provider mock` | Offline placeholder scores (no key needed) |

Important: `promos.json` reflects the **last** command. After judging episodes in separate runs, finish with `--max-calls 0` (no `--episodes`) so every cached episode is included.

Other options: `parse_show` takes `--out` and `--aliases`; `find_candidates` takes `--config`, `--out` and `--gold`. Exit code 1 means some problem was found and reported (outputs are still written); 2 means a setup problem.

## 7. Web page

Terminal 1:

```powershell
cd <repo>; .\venv\Scripts\Activate.ps1; cd backend
python manage.py runserver 127.0.0.1:8000
```

Terminal 2:

```powershell
cd <repo>\frontend
npm install
npm test           # expect 10 passed
npm run dev
```

Open http://localhost:5173: backend status, the post-first picks, the full table with episode and verdict filters, a script view for each promo and a CSV download. If it says the results come from the mock, `.env` still has `LLM_PROVIDER=mock`.

## 8. Try it on the fictional test show (no key, no confidential data)

```powershell
cd <repo>\backend
python manage.py parse_show "tests\fixtures\screenplays\clean\The Lighthouse Heir"
python manage.py find_candidates "..\data\processed\the-lighthouse-heir"
python manage.py judge_promos "..\data\processed\the-lighthouse-heir" --provider mock
```

Expect 2 episodes, 3 scenes, 11 blocks; 4 valid windows; 1 candidate; 0 hard-rule failures.

## 9. Gold set (optional, recommended)

```powershell
python -m engine.evaluation.worksheet "..\data\processed\<show-slug>"
```

This writes `data\config\gold_worksheet.md` (every spoken line with times; no candidates or scores) and a blank `data\config\gold_promos.json`, never overwriting existing picks. Choose 10 to 15 promos before opening `candidates_review.md`, fill in the JSON, re-run `find_candidates` and read the `gold` section of `candidates_report.json`.

## 10. Package the raw outputs for submission

With `make_raw_outputs.ps1` in the repo root:

```powershell
cd <repo>
powershell -ExecutionPolicy Bypass -File .\make_raw_outputs.ps1              # no API calls
powershell -ExecutionPolicy Bypass -File .\make_raw_outputs.ps1 -MaxCalls 10 # judge up to 10 more episodes first
```

It merges every cached AI answer, copies all outputs unedited to `..\Rangdrishti_raw_outputs` (outside the repo), writes `README.txt` and a SHA-256 `MANIFEST.txt`, checks for API keys and creates a zip. Upload to Google Drive and share as "Anyone with the link can view".

## 11. Publish the code

```powershell
cd <repo>
git init -b main
git add .
git status        # must NOT list data\ files, .env, db.sqlite3, venv\, node_modules\, .zip or episode-*.txt
git commit -m "Rangdrishti: promo discovery for microdrama screenplays"
gh repo create rangdrishti --public --source . --remote origin --push
```

## Daily use

```powershell
cd <repo>; .\venv\Scripts\Activate.ps1; cd backend
python manage.py parse_show ..\data\input
python manage.py find_candidates "..\data\processed\<show-slug>"
python manage.py judge_promos "..\data\processed\<show-slug>"
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Not a directory or ZIP file` | Wrong path. Type the start of it and press Tab, or check `Get-ChildItem ..\data\input`. |
| `The mock provider has no models to list` / MOCK warning | `.env` has `LLM_PROVIDER=mock`, often a duplicate line left from the template. Keep one `LLM_PROVIDER=gemini`. |
| HTTP 429 (rate limit) repeated | Free quota used up or model not in your free tier. Wait, use `--max-calls`, or switch to `gemini-2.5-flash`. Re-running is free for finished episodes. |
| HTTP 401 / 403 | Key missing, wrong or revoked: put a valid key in `.env`. |
| HTTP 400 / 404 | Model name not accepted: copy one exactly from `--list-models`, without `models/`. |
| `judge_promos` seems stuck | It prints each episode as it goes; thinking models can take 30-90 s per call and retries wait up to a minute. `Ctrl+C` is safe. |
| `FAILED: E0NN` | That episode kept its rule score. Run the same command again to retry. |
| `ModuleNotFoundError: django` | The venv is not active: `.\venv\Scripts\Activate.ps1`. |
| Port 8000 or 5173 in use | Close the other server, or check with `netstat -ano | findstr :8000`. |
| Page says "Got HTTP 500" | Django is not running in terminal 1. |
| `.env` saved as `.env.txt` | `Get-ChildItem -Force` to check, then rename it to `.env`. |
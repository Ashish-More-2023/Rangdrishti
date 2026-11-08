# Architecture decisions

## The principle: the AI judges, code measures

Language models invent plausible timestamps. So the model will never produce a timestamp. It will choose block IDs from the parsed screenplay and explain its choice. Code then turns those IDs into exact timestamps and durations, and validates them. Every layer exists to keep that boundary clean.

```
screenplay files → parser (rules) → candidate windows (rules) → AI judgement (raw JSON saved)
→ validation (code) → scoring and ranking (transparent formula) → API → dashboard
```

## Decisions and why

| Decision | Reason |
|---|---|
| Domain logic in `backend/engine/`, with no Django imports | It can be unit-tested without a database, run from a CLI to produce the raw-outputs folder, and reused if the web layer changes. |
| One Django app (`api`) | Views only parse requests and call the engine. More apps would be structure without behaviour. |
| One response envelope plus a custom DRF exception handler | The frontend handles every success and error the same way. Tracebacks never reach the client. |
| Health check also tests the database | It proves the backend can actually do work, not just that the process is alive. |
| Authentication off, JSON renderer only | There are no users yet. Fewer moving parts and no CSRF or session setup. |
| SQLite | Free, zero setup, and enough for one show of results. |
| Vite proxy by default, CORS also configured | The proxy avoids cross-origin issues in development. CORS covers the case where frontend and backend are hosted separately. |
| Proxy target is 127.0.0.1, not localhost | On Windows, Node can resolve localhost to IPv6 (::1) while Django's runserver listens on IPv4 only. |
| Settings from environment variables | No secrets in Git. The app refuses to start without `DJANGO_SECRET_KEY` when debug is off. |
| `data/` ignored by Git, raw and processed outputs in separate folders | Protects Kuku's confidential content and keeps unedited model output apart from validated results, as the brief requires. |
| Dependency ranges capped at known-compatible versions | Stability over novelty: Django 5.2 LTS with DRF 3.16. |

## Facts about the input pack that shape later stages

- 50 episodes, 100 scenes and 3,727 timed blocks, one UTF-8 `.txt` file per episode with no trailing newline (about 103 minutes in total).
- Timestamps restart in every episode, so a promo is a list of (episode, start, end) segments.
- Camera, action and dialogue blocks overlap in time. A clip's length is first start to last end, not the sum of block durations.
- The format varies: episode 6 uses upper-case scene headers, some labels carry two parentheticals (`MARA (V.O.) (Reflective)`), and characters appear under several names (`LADY MARA` / `MARA`).
- Episodes often end on a scripted cliffhanger. The tool must not settle for episode endings.

## Stage 2 decisions

| Decision | Reason |
|---|---|
| Stage 2 reads only show.json | Each stage depends on the previous stage's versioned output, not on raw files. |
| Rules shortlist, AI judges later | 16,837 valid windows is too many to send to a free-tier model; rules cut it to about 230 with reasons. |
| Structure first, keywords capped at 0.15 | Explicit drama words are rare in the scripts; timing and delivery tags generalise to new shows. |
| Validator re-implements the clean-cut check | Two independent implementations catch each other's bugs; it is reused for AI output later. |
| Weights in a versioned JSON config with a hash on every output | Tunable without code changes; any output can be traced to the exact settings. |
| Human gold set with a random baseline | The only honest way to show the rules help; code never writes the picks. |

## Planned AI provider design (not built yet)

A small interface with two adapters: a `MockProvider` for tests and offline runs, and one `OpenAICompatibleProvider` configured by base URL, model and key. The second covers Ollama (local and free), Groq, OpenRouter, and Gemini's compatible endpoint, so swapping models means changing environment variables, not code.

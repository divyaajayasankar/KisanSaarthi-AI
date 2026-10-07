# KisanSaarthi AI: Deployment and Integration

Version for the final review, 2026-10-08. Every claim below is marked with how it was checked.

## What was verified, and how

| Item | State | Evidence |
|---|---|---|
| Local run on Windows (`run_project.ps1`) | Verified | Run on the project laptop |
| Live-server smoke test (`scripts/smoke_test.py`) | Verified in the build sandbox against a real uvicorn process: 7 of 7 checks | Passed 6 of 6 on the project laptop with the real registry and live weather; also 7 of 7 in the build sandbox |
| Chat web UI plus REST API | Verified | pytest suite, all passing |
| WhatsApp Cloud API adapter | Verified with simulated Meta payloads only (verification handshake, signature check, text, photo, location, voice note, send path with a recorded Graph API client) | `tests/test_whatsapp_adapter.py`, 16 tests. Not tested against live WhatsApp. |
| Docker image and compose file | Written. Compose file passes `docker compose config`. The image was not built because neither the sandbox nor the project laptop has a running Docker daemon. | Treat as untested until you run `docker compose up --build` |
| PostgreSQL | One code change: the SQLite-only connection argument is skipped for other databases (`app/db.py`, 2 tests). Not run against a PostgreSQL server. | Untested |
| Celery, Redis, MinIO, LangChain | Not used | Not built |

## Architecture

```
Farmer
  |-- Browser chat UI (text, photo, GPS) ------\
  |-- WhatsApp (text, photo, shared location) --+--> FastAPI app (uvicorn)
                                                       |
                         handle_turn: one conversation engine for both channels
                                                       |
   Context agent -> Location agent -> Vision agent (Grad-CAM region) -> Pest alias layer
        -> Treatment history agent -> Safety engine (dose, area, PHI, stage, interval, weather)
        -> Decision controller (ANSWER / ASK_FOLLOW_UP / ABSTAIN) -> reply in en, hi, ta, te
                                                       |
                       SQLite (or PostgreSQL via DATABASE_URL): registry, sessions,
                       advisory_traces, field_profiles;  logs/kisansaarthi.log
```

The same `handle_turn` function serves the browser and WhatsApp, so a WhatsApp number is one persistent field session.

## Run on Windows (tested)

```powershell
.\run_project.ps1 -SkipInstall
```

Open http://127.0.0.1:8000. In a second PowerShell window, with the server running:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test --base-url http://127.0.0.1:8000
```

The smoke test checks health, status, a full chat conversation, the saved trace and profile, and the WhatsApp webhook. Exit code 0 means every check passed. A weather hold (rain, wind, or an unverified forecast) passes only if the reply carries the planned dose.

## Run with Docker (untested image)

```bash
cp .env.example .env        # then fill in OPENWEATHER_API_KEY
mkdir -p db && cp kisansaarthi.db db/
docker compose up --build
```

The app listens on port 8000. `./db`, `./logs` and `./data/uploads` are mounted so data survives container restarts. The build installs PyTorch CPU wheels (large) so the banana and chilli models can run; set `WITH_VISION: "false"` in `docker-compose.yml` for a smaller image without photo diagnosis.

### PostgreSQL (optional, untested)

```bash
pip install -r requirements-postgres.txt
```

In `.env` set `POSTGRES_PASSWORD` and `DATABASE_URL=postgresql+psycopg2://kisan:<password>@postgres:5432/kisansaarthi`, then run `docker compose --profile postgres up --build`. Tables are created at startup. The registry rows must be loaded into the new database; the project's seed and import scripts write to whatever `DATABASE_URL` points at.

## WhatsApp setup (to go live)

1. Create a Meta developer app and add the WhatsApp product. Note the phone number ID and create a permanent access token.
2. Put these in `.env`: `WHATSAPP_VERIFY_TOKEN` (any string you choose), `WHATSAPP_APP_SECRET` (the app secret, enables signature checking), `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`.
3. Expose the server over HTTPS (a reverse proxy or a tunnel). Meta requires a public HTTPS URL.
4. In the Meta webhook settings, set the callback URL to `https://<your-host>/api/whatsapp/webhook`, the verify token to the same string, and subscribe to `messages`.
5. Send a text, a leaf photo or a shared location from a phone. The reply returns through the Graph API.

Meta limits free-form replies to a window after the user's last message; check Meta's current rules before relying on proactive messages. Voice notes get a fixed "not supported yet" reply.

Without the access token and phone number ID the adapter runs as a dry run: the reply comes back in the HTTP response, which is how the tests and the smoke test use it.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `OPENWEATHER_API_KEY` | Forecast and place lookup. Without it every advisory stops at "weather could not be verified", still showing the planned dose. | empty |
| `DATABASE_URL` | SQLite file or PostgreSQL URL | `sqlite:///./kisansaarthi.db` |
| `LLM_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional wording and translation help. The LLM never computes doses, intervals, areas or decisions. | disabled |
| `VISION_ANSWER_THRESHOLD`, `VISION_ASK_THRESHOLD` | Photo confidence cut-offs | 0.80, 0.55 |
| `WHATSAPP_*` (four variables) | WhatsApp adapter | empty (dry run) |

## Security checklist

- `.env` is git-ignored and `scripts.package_project` refuses to put it, or any file matching key patterns, in the ZIP.
- The ZIP carries no farmer data: `farmer_profiles`, `advisory_runs`, `conversation_sessions`, `advisory_traces` and `field_profiles` are emptied in the frozen database.
- Webhook POSTs are rejected with 403 when `WHATSAPP_APP_SECRET` is set and the `X-Hub-Signature-256` header is wrong or missing. The verify token is compared in constant time.
- WhatsApp tokens are read from the environment at request time and never written to logs or the database.
- Uploaded photos go to `data/uploads/<session>/`, which is excluded from git, the ZIP and the Docker build context.
- Rotate any API key that was ever pasted into a chat or a document. The OpenWeather key used during development must be regenerated after the review.

## Monitoring

- `GET /health` for liveness (used by the Docker `HEALTHCHECK`).
- `GET /api/status` for registry rows, crops with validated models, and whether the vision runtime loaded.
- `logs/kisansaarthi.log` (rotating, 1 MB x 3) and the console.
- `GET /api/chat/trace/{session_id}` returns every turn with the agents run, fired rules, decision and latency, stored in `advisory_traces`.

## Rollback and backup

Copy `kisansaarthi.db` before every change. To roll back code, restore the previous ZIP or the earlier commit on `final-submission`; the patch scripts keep a `_backup_addons_<time>` folder of every file they replaced. No migration is needed for the code in this release: new tables are created at startup and nothing is dropped.

## Known limits

- Photo diagnosis and affected region work for two crops (banana, chilli). The held-out macro-F1 scores (banana 0.9722, chilli 0.8893) come from splits of their own training datasets and are not field accuracy. The chilli dataset source and licence are still TO_VERIFY. The region is a Grad-CAM attention map (where the model looked), not a measured lesion area.
- Other crops accept text queries and return registered doses, but a photo for them gets an honest "no validated model" note.
- The planned dose is shown only when weather is the sole blocker. PHI, growth-stage, interval and application-cap blocks show no dose.
- Retrieval is keyword matching over a small verified knowledge file, not a 50,000-page document index.
- Hindi, Tamil and Telugu text has not been reviewed by native speakers.

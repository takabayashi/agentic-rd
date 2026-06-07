# Wikipedia Edit-Triage Agent

[![CI](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml/badge.svg)](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml)

A locally-runnable system that ingests the Wikipedia recent-changes firehose,
triages each edit with a multi-step LLM reasoning loop (Redpanda Connect +
Ollama), and serves the results on a live dashboard. Built for the Redpanda
Field Deployed Engineer build exercise.

> Status: **Phase 3** — the dashboard reads classified edits from Postgres
> (seeded sample rows for now). Ingest, transform, and the LLM loop land in
> later phases (see [`docs/TODO.md`](docs/TODO.md)).

## Run

```bash
docker compose up
```

This starts Postgres (schema + seed applied automatically on first run) and the
web app. Open <http://localhost:8080> to see the triage dashboard, served from
the seeded rows in [`db/seed.sql`](db/seed.sql).

Health check:

```bash
curl localhost:8080/healthz   # -> HTTP 200 (liveness; does not require the DB)
```

If you open the dashboard before Postgres is ready, you get a 503 "warming up"
page that auto-retries — the app never crashes on a cold or transient DB.

## Dashboard & API

- `GET /` — HTML dashboard: a table of classified edits sorted by confidence
  descending, with label-filter chips (`all/vandalism/substantive/trivia/unclear`)
  and a 15-second auto-refresh. The page is rendered in plain Python (no
  template engine); untrusted fields (title, comment, editor) are escaped with
  `html.escape`, diff links are emitted only for `http(s)` URIs and carry
  `rel="noopener noreferrer"`.
- `GET /api/edits?label=<label>` — the same data as JSON, newest-highest-
  confidence first. Omitting `label` (or `all`) returns everything. Each row:

```json
{
  "rev_id": 1300000002,
  "title": "List of common misconceptions",
  "editor": "192.0.2.51",
  "comment": "…",
  "label": "vandalism",
  "confidence": 0.97,
  "escalated": false,
  "size_delta": -512,
  "uri": "https://en.wikipedia.org/w/index.php?diff=1300000002",
  "event_ts": "2026-06-07T12:00:00Z",
  "classified_at": "2026-06-07T12:00:00Z"
}
```

## Database

Schema lives in [`db/init.sql`](db/init.sql); sample rows in
[`db/seed.sql`](db/seed.sql). Both are applied by the Postgres image's
init-entrypoint **only on first start** of an empty data volume. To re-apply
after editing them, recreate the volume:

```bash
docker compose down -v && docker compose up
```

Connect with `psql`:

```bash
docker compose exec postgres psql -U wiki -d wiki -c "SELECT rev_id, label, confidence FROM classified_edits ORDER BY confidence DESC;"
```

`classified_edits` columns: `rev_id` (BIGINT PK), `title`, `editor`, `comment`,
`label` (TEXT + CHECK enum `vandalism|substantive|trivia|unclear`), `confidence`
(0–1), `escalated`, `size_delta`, `uri`, `event_ts` (TIMESTAMPTZ), `classified_at`.

`rev_id` is the primary key so the pipeline (Phase 9) can UPSERT
(`ON CONFLICT (rev_id) DO UPDATE`): a row first classified `unclear` on a
cold-start/transient failure is corrected in place by a later, more confident
pass — no duplicates, no PK collisions. The `label` CHECK rejects any
out-of-enum value at the database boundary. DB credentials come from env only
(`POSTGRES_*` / `DATABASE_URL`); change the default password for any
non-throwaway use.

The dashboard's empty state shows automatically whenever the table has no rows
(for example, on a fresh volume before the pipeline runs).

## Develop / test

```bash
cd app
pip install -r requirements.txt
pytest
```

Layout:

```text
app/
  triage/            # the application package
    main.py          # composition root: builds the app + wires the router
    models.py        # EditView + Label enum + select_edits()  (domain)
    repository.py    # Postgres access: get_recent_edits, DatabaseUnavailable  (data)
    web.py           # HTTP layer: APIRouter (dashboard, /api/edits, /healthz) + view helpers
    render.py        # plain-Python HTML rendering (html.escape on untrusted fields)
  tests/             # pytest suite + sample_data fixture
  Dockerfile
  requirements.txt
db/                  # init.sql (schema) + seed.sql
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed. `.env` is gitignored — no
secrets are committed. `.env` is optional: `docker-compose.yml` supplies safe
local defaults (including the Postgres credentials), so a fresh clone runs with
just `docker compose up`.

## CI

Every push and pull request runs a deliberately small GitHub Actions workflow
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) with least-privilege
`GITHUB_TOKEN` permissions (`contents: read`). The brief doesn't ask for CI, so
this is kept minimal — just enough to keep the repo trustworthy. Jobs:

| Job        | What it checks                                              |
|------------|------------------------------------------------------------|
| `lint`     | `ruff check` + `ruff format --check` (config: `ruff.toml`) |
| `yamllint` | YAML style (config: `.yamllint.yml`)                       |
| `hadolint` | `app/Dockerfile` best practices                            |
| `test`     | `pytest`                                                   |
| `build`    | `docker compose build` (proves images build)               |
| `gitleaks` | secret scan over full git history                          |

Run the same checks locally:

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
yamllint .
(cd app && pip install -r requirements.txt && pytest -q)
docker compose build
```

Deploy automation, dependency bots, and branch protection are intentionally out
of scope (see [`docs/TODO.md`](docs/TODO.md) "Out of scope").

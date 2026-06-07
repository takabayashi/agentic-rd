# Wikipedia Edit-Triage Agent

[![CI](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml/badge.svg)](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml)

A locally-runnable system that ingests the Wikipedia recent-changes firehose,
triages each edit with a multi-step LLM reasoning loop (Redpanda Connect +
Ollama), and serves the results on a live dashboard. Built for the Redpanda
Field Deployed Engineer build exercise.

> Status: **Phase 2** — moderator dashboard served from a mocked fixture. Ingest,
> transform, LLM, and the Postgres-backed store land in later phases (see
> [`docs/TODO.md`](docs/TODO.md)).

## Run

```bash
docker compose up
```

Then open <http://localhost:8080> to see the triage dashboard (currently fed by
a hardcoded fixture).

Health check:

```bash
curl localhost:8080/healthz   # -> HTTP 200
```

## Dashboard & API

- `GET /` — HTML dashboard: a table of classified edits sorted by confidence
  descending, with label-filter chips (`all/vandalism/substantive/trivia/unclear`)
  and a 15-second auto-refresh. Untrusted fields (title, comment) are
  HTML-escaped; external diff links carry `rel="noopener noreferrer"`.
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

Set `AGENTIC_EMPTY=1` to preview the empty state.

## Develop / test

```bash
cd app
pip install -r requirements.txt
pytest
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed. `.env` is gitignored — no
secrets are committed. Phase 0 requires no configuration.

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

# Configuration & CI

[← Back to README](../README.md)

## Configuration

Copy `.env.example` to `.env` and adjust as needed (`./start.sh` does this on
first run). `.env` is gitignored. `.env` is optional — `docker-compose.yml` uses
fixed local DB credentials (`wiki` / `change-me`) and supplies defaults for
everything else, so a fresh clone runs with just `docker compose up`.

| Variable | Default | Used by | Purpose |
|----------|---------|---------|---------|
| *(fixed in compose)* `wiki` / `change-me` / `wiki` | — | postgres, app, classify | Local-only DB credentials baked into `docker-compose.yml` |
| `RECENT_WINDOW_LIMIT` | `200` | app | recent rows fetched before in-app filter/sort |
| `WIKI_USER_AGENT` | repo default | ingest, enrich | Wikipedia requires a descriptive UA (403 otherwise) |
| `DIFF_MAX_CHARS` | `4000` | enrich | truncate fetched diffs to this many chars |
| `WIKI_RATE_LIMIT` | `10` | enrich | MediaWiki compare-API calls/sec (politeness) |
| `OLLAMA_MODEL` / `OLLAMA_ADDRESS` | `llama3.2` / `http://ollama:11434` | classify, pull | model + server (set host address on Apple Silicon) |
| `CONFIDENCE_THRESHOLD` | `0.7` | classify | escalate edits below this confidence |
| `DIFF_MIN_CHARS` | `1` | classify | content gate: cleaned-diff length below this is "empty" |
| `BLANKING_MIN_DELTA` | `100` | classify | content gate: keep edits with `\|size_delta\|` ≥ this (blanking/large removals still hit the model) |

**Secrets.** Credentials come only from env/`.env` (never tracked); SQL is
parameterized and DSNs carry no creds in logs. For a real deployment, move the DB
password to Docker/Compose secrets or an external manager (Vault, cloud secrets)
and scope topic ACLs — the local default flow is convenience, not a production
secret posture.

## CI

Every push and pull request runs a deliberately small GitHub Actions workflow
([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) with least-privilege
`GITHUB_TOKEN` permissions (`contents: read`). CI is intentionally minimal — just
enough to keep the repo trustworthy. Jobs:

| Job        | What it checks                                              |
|------------|------------------------------------------------------------|
| `lint`     | `ruff check` + `ruff format --check` (config: `ruff.toml`) |
| `yamllint` | YAML style (config: `.yamllint.yml`)                       |
| `hadolint` | `app/Dockerfile` best practices                            |
| `test`     | `pytest` (incl. testcontainers integration test on Docker) |
| `connect-lint` | `connect lint` all pipelines + Connect Bloblang unit tests |
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
of scope (see [`TODO.md`](TODO.md) "Out of scope").

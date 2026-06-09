# Develop & test

[← Back to README](../README.md)

A root [`Makefile`](../Makefile) wraps the common workflow — run `make help` for
the full list. Highlights:

```bash
make start         # one-command bootstrap (./start.sh)
make up            # docker compose up -d
make logs-connect  # follow the pipeline
make labels        # label distribution from the logs
make escalations   # escalated:true vs false counts
make diffs         # recent diff-fetch lines (rev_id + diff_chars)
make topics        # list topics; make consume-classified / consume-audit
make psql          # psql shell on Postgres
make connect-test  # Connect Bloblang unit tests (parse/normalize/clamp)
make check         # ruff + yamllint + connect-lint + pytest (local CI)
```

**Live edits (no rebuild).** The `webapp` service runs uvicorn with `--reload`
and bind-mounts `app/triage` and `app/static` over the image, so editing the
dashboard assets (`app/static/dashboard.css`, `dashboard.js`) or the Python code
is picked up live — just refresh the browser. The baked image is still the source
of truth on a fresh clone and in CI; the mounts only overlay it in dev.

## Testing

The core suite is **DB-free**: it mocks `get_recent_edits` with an in-memory
fixture, so `make test` runs without Postgres or the broker. One optional
integration test
([`app/tests/test_integration_db.py`](../app/tests/test_integration_db.py)) spins
up a throwaway Postgres via testcontainers and **skips automatically when Docker
isn't available**, so it never blocks the DB-free path.

Run tests with `make test` (which does `cd app && pytest`, so the `triage`
package resolves). Bare `pytest` from the repo root does **not** work by design —
`app/pytest.ini`'s `pythonpath` only applies from `app/`; always use `make test`
or `cd app && pytest`.

```bash
make install   # app + dev deps (in your virtualenv)
make test      # pytest in app/  (DB-free; integration test skips w/o Docker)
make check     # full local CI mirror (lint + yamllint + connect-lint + test)
```

**What's covered**

| Area | Module / file | Edge cases |
|------|----------------|------------|
| Dashboard & API | `tests/test_dashboard.py` | label + escalated filters, pagination, JSON shape, empty state, 503 warm-up, XSS escape, live-feed fragment |
| Health/metrics | `tests/test_health.py` | `/healthz` liveness, `/readyz` ready/down, `/metrics` exposition |
| Repository | `tests/test_repository.py` | parameterized `LIMIT %s`, `DatabaseUnavailable` mapping, `check_ready` |
| Schema contract | `tests/test_schema_contract.py` | `EditView` ↔ `db/init.sql` agree |
| Integration | `tests/test_integration_db.py` | real Postgres via testcontainers (skips if Docker absent) |

Connect Bloblang has a real unit-test harness too: `make connect-test` runs the
parse/normalize/clamp cases ([`connect/tests/`](../connect/tests/)) against the
actual shared library
([`connect/lib/classification.blobl`](../connect/lib/classification.blobl)), and
`make connect-lint` validates every pipeline config. Live e2e remains the final
check.

## Layout

```text
start.sh             # one-command bootstrap (preflight, .env, wait-for-health)
install.sh           # curl | bash fresh-machine installer (clones + start.sh)
app/
  triage/            # the application package
    main.py          # composition root: app + router + metrics + JSON logging
    config.py        # typed settings (pydantic-settings)  (config)
    models.py        # EditView + Label enum + select_edits()  (domain)
    repository.py    # Postgres access: get_recent_edits, check_ready  (data)
    web.py           # HTTP layer: dashboard, /fragment/edits, /api/edits, /healthz, /readyz, /metrics
    render.py        # plain-Python HTML rendering (links the static assets)
    metrics.py       # Prometheus middleware + /metrics payload
    logging_config.py # one-line JSON logging
  static/            # dashboard assets served at /static (dashboard.css/js, warmup.css)
  tests/             # pytest suite + sample_data fixture
  Dockerfile
  requirements.txt
db/                  # init.sql (first-boot schema) + seed.sql
connect/             # ingest/enrich/classify pipelines + lib/ (shared Bloblang) + tests/
Makefile             # dev/test shortcuts (make help)
```

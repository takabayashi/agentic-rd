# Decisions Log

Meaningful tech-stack, library, strategy, and architecture decisions, grouped by
phase. Newest entries are appended; past entries are never deleted (superseding
entries reference the ones they replace).

## Phase 0 — Project initialization & "Hello World"

### Web app framework: FastAPI + Uvicorn
- **Decision:** Serve the dashboard/API with FastAPI (`0.136.3`) on Uvicorn (`0.49.0`).
- **Alternatives:** Flask, bare Starlette, Django.
- **Rationale / trade-offs:** PRD left the web framework open ("plain but works"). FastAPI gives typed routes, built-in JSON, and a test client with minimal boilerplate; Jinja2 templating (Phase 2) is first-class. Heavier than bare Starlette but far lighter than Django for a single-table dashboard.
- **Made by:** Agent
- **Date:** 2026-06-05

### Base image: pinned `python:3.12.13-slim`
- **Decision:** Build the webapp from `python:3.12.13-slim` (exact patch pin, not `:latest` or floating `3.12-slim`).
- **Alternatives:** `python:3.12-slim` (floating), `-alpine`, `-bookworm` (full).
- **Rationale / trade-offs:** Exact pin makes builds reproducible (security task requires pinned tags). `slim` over `alpine` avoids musl/wheel friction; over full `bookworm` to keep the image small.
- **Made by:** Agent
- **Date:** 2026-06-05

### Test dependencies live in `app/requirements.txt`
- **Decision:** Keep `pytest` and `httpx` in the same pinned `requirements.txt` as runtime deps rather than a separate `requirements-dev.txt`.
- **Alternatives:** Split dev/runtime requirement files; use a `pyproject.toml` with extras.
- **Rationale / trade-offs:** One pin set keeps CI (Phase 1) and `pytest` aligned with zero drift for a small project. Trade-off: test libs ship in the image; acceptable at this scale and revisitable if image size matters.
- **Made by:** Agent
- **Date:** 2026-06-05

### `docker-compose.yml`: optional `.env`
- **Decision:** Reference `.env` with `required: false` so `docker compose up` works on a fresh clone with no `.env` present.
- **Alternatives:** Require `.env`; commit a default `.env`.
- **Rationale / trade-offs:** Preserves the one-command-run guarantee without committing secrets. Phase 0 needs no config; later phases add real env vars (documented in `.env.example`).
- **Made by:** Agent
- **Date:** 2026-06-05

## Phase 1 — CI/CD pipeline

### CI platform: GitHub Actions
- **Decision:** Run lint/test/build/secret-scan as GitHub Actions on push + PR; one `ci.yml` with parallel jobs, a separate `deploy.yml` for tag-triggered publish.
- **Alternatives:** GitLab CI, CircleCI, a single monolithic job.
- **Rationale / trade-offs:** Repo is already on GitHub; Actions needs no extra accounts (PRD: free/local). Parallel jobs give fast, independently-readable signal; splitting deploy keeps the PR pipeline free of registry permissions.
- **Made by:** Agent
- **Date:** 2026-06-05

### Lint/format: ruff (check + format) via `ruff.toml`
- **Decision:** Use ruff for both linting and format-checking, configured in a root `ruff.toml` (line-length 100; rules E/F/W/I/UP/B).
- **Alternatives:** flake8 + black + isort (separate tools), pylint.
- **Rationale / trade-offs:** One fast Rust binary replaces three tools and stays internally consistent (no black-vs-isort conflicts). Trade-off: ruff format is newer than black, but it's black-compatible and the codebase is tiny.
- **Made by:** Agent
- **Date:** 2026-06-05

### Lint tooling pinned in `requirements-dev.txt` (separate from the image)
- **Decision:** Keep `ruff`/`yamllint` in a root `requirements-dev.txt`, distinct from `app/requirements.txt`.
- **Alternatives:** Add lint tools to `app/requirements.txt` (mirrors the Phase 0 test-deps decision); install unpinned in CI.
- **Rationale / trade-offs:** Lint tools are never needed at runtime, so shipping them in the webapp image (as test deps are) adds no value and bloats it. Pinning keeps CI reproducible. This intentionally diverges from the Phase 0 "one pin set" call because the audience differs (image vs. CI-only).
- **Made by:** Agent
- **Date:** 2026-06-05

### Secret scan: gitleaks binary (not the marketplace action)
- **Decision:** Download the pinned `gitleaks` binary in CI and run `gitleaks detect` over full history (`fetch-depth: 0`).
- **Alternatives:** `gitleaks/gitleaks-action@v2`.
- **Rationale / trade-offs:** The official action gates org-owned repos behind a license key; the raw binary is Apache-2.0 and license-free, keeping the repo trivially forkable. Trade-off: we pin/bump the version ourselves (Dependabot doesn't track a shell download).
- **Made by:** Agent
- **Date:** 2026-06-05

### Deploy: publish to GHCR on `v*` tags (least-privilege)
- **Decision:** `deploy.yml` builds `app/` and pushes to `ghcr.io/<repo>-webapp` only on version tags, using `permissions: packages: write` (CI default stays `contents: read`).
- **Alternatives:** Docker Hub, deploy on every main push, no automated publish (docs only).
- **Rationale / trade-offs:** GHCR needs no extra secrets (built-in `GITHUB_TOKEN`). Tag-gating avoids publishing every commit; scoping `packages: write` to the deploy workflow keeps the PR pipeline read-only. A manual `docker push` fallback is documented for environments without tagging.
- **Made by:** Agent
- **Date:** 2026-06-05

## Planning — Scope revalidation against the brief

### Consolidate the build plan (13 phases → 10) and cap scope
- **Decision:** Revalidated `requirements.md` + `TODO.md` against the take-home brief and trimmed for the explicit "couple-of-hours / plain but works" framing. Merged Connect ingest + transform (now Phase 4), merged Ollama infra + pass-1 classify (Phase 5), and folded the standalone "observability" phase's useful parts (output retries/backoff + clean logs) into the end-to-end dual-sink phase (Phase 7) while dropping the metrics/counter view. Trimmed UI and test scope. Kept the required README write-up as its own final phase (Phase 9) because it is the most heavily graded artifact.
- **Alternatives:** Keep the granular 13-phase plan; cut Postgres and serve only a topic; drop the second LLM pass.
- **Rationale / trade-offs:** The brief grades judgment and "names the cuts", not surface area, and warns against gold-plating. The consolidated plan still covers every asked deliverable (ingest → transform → reason → serve, README write-up, one-command run) and every evaluation dimension (connector fluency incl. retries/error paths, data sense, multi-step agent design, output usability, local repro, architectural reasoning). Dual sink (topic + Postgres) is kept deliberately because it directly feeds two of the brief's Tradeoffs pairs. We gave up granular per-step verifiability for a leaner, more honest plan.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Cap CI/CD at the minimal setup already in place
- **Decision:** Treat the existing lint/test/build/secret-scan CI as sufficient and do **not** expand CI/CD. GHCR deploy (`deploy.yml`), Dependabot, branch protection, and the hadolint/yamllint jobs are reframed as extras beyond the brief (kept since already built, but not grown); recorded under Out of Scope.
- **Alternatives:** Continue building out CI/CD (more linters, environments, release automation); or delete the already-built deploy/Dependabot config entirely.
- **Rationale / trade-offs:** The brief never asks for CI; over-investing there spends the "couple of hours" away from the graded ingest→reason→serve path. Keeping the built pieces avoids churn/regressions; not expanding them avoids gold-plating. Deleting them was rejected as needless rework with no scoring upside. Supersedes the implied "CI is a first-class scope area" stance from the Phase 1 entries above.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Remove `deploy.yml` + `dependabot.yml` (supersedes the two entries above)
- **Decision:** Deleted `.github/workflows/deploy.yml` (GHCR publish) and `.github/dependabot.yml`. CI is now just `ci.yml` (lint/test/build/secret-scan). Supersedes the "Deploy: publish to GHCR" entry and the "kept since already built" stance of the cap-CI entry.
- **Alternatives:** Keep them dormant (prior decision).
- **Rationale / trade-offs:** Human chose a leaner, brief-aligned repo footprint. The deploy/dependabot config carried maintenance surface (version bumps, token scopes) for zero scoring upside on a local-run exercise. Trade-off: a future real deployment re-adds a release workflow, but that's out of scope here.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

## Phase 2 — Dashboard with mocked data

### Server-rendered Jinja2 dashboard (not a client-side SPA)
- **Decision:** Render `/` server-side with Jinja2 templates; auto-refresh via a plain `<meta http-equiv="refresh">`. A parallel `GET /api/edits` returns JSON.
- **Alternatives:** React/Vue SPA fetching the JSON API; HTMX partial updates; websockets/SSE push.
- **Rationale / trade-offs:** The brief wants "plain but works" and a result a person can act on. Server rendering needs no build step, ships in the existing FastAPI image, and is trivially testable via the test client. Meta-refresh is cruder than HTMX/websockets but adequate for a seconds-fresh triage feed. The JSON endpoint keeps a clean seam for a richer UI later. Autoescaping (on by default) is load-bearing here because titles/comments are attacker-controlled.
- **Made by:** Agent
- **Date:** 2026-06-07

### Pydantic `EditView` as the single view-model + `load_edits()` data seam
- **Decision:** Define one pydantic `EditView` (+ `Label` enum) in `models.py` as the contract for both the HTML view and the JSON API; the web layer pulls data through `mock_data.load_edits()`, a thin seam Phase 3 swaps for a Postgres repository without touching routes.
- **Alternatives:** Return raw dicts/ORM rows to the template; query the data source directly inside the route handlers.
- **Rationale / trade-offs:** One typed contract keeps the UI, API, and (later) the DB schema in agreement and gives free, correct JSON serialization (datetimes → ISO, enum → value), pre-satisfying the pipeline's "epoch → ISO" rule at the serving edge. The `load_edits()` indirection is a deliberate, minimal seam (not a speculative repository interface) so the mock→Postgres swap is a one-module change. Cost: a little ceremony for what is still a single table.
- **Made by:** Agent
- **Date:** 2026-06-07

## Phase 3 — Postgres: schema, seeds, real serving

### psycopg 3 + `psycopg-pool` (over psycopg2 / per-request connect)
- **Decision:** Use psycopg 3 (`psycopg[binary]`) with a lazily-opened `ConnectionPool` (`open=False`, `check=check_connection`, short timeouts) in `app/db.py`; `get_recent_edits()` is the data seam (supersedes `mock_data.load_edits` in the runtime path).
- **Alternatives:** psycopg2; a fresh `psycopg.connect()` per request (no pool); an async driver (asyncpg) with async routes.
- **Rationale / trade-offs:** psycopg 3 is current and ships a maintained pool. A pool fits FastAPI's threadpool (sync routes) and amortizes connection cost; `check_connection` makes it self-heal after a Postgres restart (validated). `open=False` means importing the module never connects, so tests/CI stay DB-free. The `[binary]` wheel bundles libpq, so the Dockerfile needs no system packages. Per-request connect was simpler but re-pays TCP+auth each call and still needs the same error handling; asyncpg would force async routes for little gain at this scale.
- **Made by:** Agent
- **Date:** 2026-06-07

### `label` as a TEXT + CHECK constraint (not a PG ENUM type)
- **Decision:** Store `label` as `TEXT NOT NULL CHECK (label IN (...))`.
- **Alternatives:** A native Postgres `ENUM` type; no DB-level constraint (validate only in the app).
- **Rationale / trade-offs:** CHECK gives the same "reject out-of-enum at the DB boundary" guarantee (validated) while keeping label changes to a one-line constraint edit instead of `ALTER TYPE ... ADD VALUE` (which has its own transactional quirks). Maps cleanly to/from the pydantic `Label` enum. Trade-off: no enumerable type in the catalog, which we don't need.
- **Made by:** Agent
- **Date:** 2026-06-07

### Schema + seed via the image init-entrypoint; graceful-503 over hard dependency
- **Decision:** Mount `db/init.sql` + `db/seed.sql` into `/docker-entrypoint-initdb.d/`; gate `webapp` on `postgres` `service_healthy`; and still wrap reads so a missing/slow DB returns a 503 warm-up page (HTML) / JSON rather than crashing. `/healthz` stays DB-independent (liveness).
- **Alternatives:** Run migrations from the app on startup (e.g. Alembic); make the app hard-fail if the DB is down; check the DB inside `/healthz`.
- **Rationale / trade-offs:** initdb scripts are zero-extra-tooling for a single-table schema and double as the "seeds" deliverable; the cost is they run only on an empty volume (documented `down -v` to re-seed). The healthcheck gate shrinks the cold-start window, but the 503 fallback is what actually satisfies "transient DB outage is not fatal; restarting recovers" and the later cold-start-LLM correction story. Keeping `/healthz` DB-free means the container is judged live even while it serves the warm-up page. Alembic is deferred — overkill before the schema is exercised by the pipeline.
- **Made by:** Agent
- **Date:** 2026-06-07

### Restructure `app/` into a `triage/` package
- **Decision:** Move the flat modules into a single application package: `app/triage/{__init__,main,models,repository,templates/}` with `repository.py` renamed from `db.py`; keep tests at `app/tests/` and move the mock fixture there as `sample_data.py`. Intra-package imports are relative (`from .models import ...`); tests import `from triage... import ...`. Dockerfile entrypoint becomes `uvicorn triage.main:app`.
- **Alternatives:** Keep the flat module layout; go further with layered subpackages (`domain/`, `data/`, `web/`); promote to a repo-root `src/` layout with `pyproject.toml`.
- **Rationale / trade-offs:** A flat folder of `main/models/db/mock_data` had no package boundary and mixed a test fixture in with production code. A single package gives one clear import root and a place for each concern (routes / domain / data access / templates) without the ceremony of layered subpackages or packaging metadata, which would be over-engineering for ~4 modules. `mock_data` moved under `tests/` because it is test/dev-only now that production reads from Postgres. Cost: a one-time import + entrypoint churn and an image rebuild.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Extract a `triage/web/` subpackage (HTTP layer) from `main.py`
- **Decision:** Move the routes, presentation helpers, and templates into `triage/web/` (`routes.py` = `APIRouter` with `dashboard`/`api_edits`/`healthz` + the `Jinja2Templates` instance; `presentation.py` = framework-free `FILTERS` + `label_counts()`; `templates/`). `main.py` becomes a thin composition root (`FastAPI(...)` + `lifespan` + `include_router`). Tests patch `triage.web.routes.get_recent_edits`.
- **Alternatives:** Keep routes in `main.py` (prior state); a single `web.py` module instead of a subpackage.
- **Rationale / trade-offs:** Completes the layering so the HTTP concern is symmetric with the already-split domain (`models`) and data (`repository`) layers, and `main.py` reads as an obvious wiring root. Keeping `presentation.py` free of FastAPI imports makes the view logic unit-testable in isolation. The cost is more files for a small, feature-complete webapp (3 routes) and a moved monkeypatch target (`get_recent_edits` is now looked up in `web.routes`). Chosen over a single `web.py` for room to grow and clearer separation of pure vs. HTTP code; this was a deliberate structure choice the human asked for over the lighter option.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Drop Jinja2 for plain-Python HTML rendering (`render.py`)
- **Decision:** Remove the `jinja2` dependency and the `templates/` files; render the dashboard and warm-up page from `triage/render.py` using f-strings, escaping every untrusted field with stdlib `html.escape(..., quote=True)` and only emitting diff links for `http(s)` URIs. `web.py` returns `HTMLResponse(render_...())`.
- **Alternatives:** Keep Jinja2 (autoescaping + template separation); a small HTML-builder lib (`htpy`/`dominate`); a Python UI framework (Streamlit/NiceGUI).
- **Rationale / trade-offs:** For a single table + a warm-up page, a template engine is more machinery than the job needs; dropping it removes a dependency and two files with no feature loss, keeping the FastAPI app, JSON API, `/healthz`, and `TestClient` tests intact. The real risk — XSS via attacker-controlled title/comment — is handled explicitly with `html.escape` (one `_esc` helper, asserted by the existing escaping test) plus an http-only href guard. Streamlit/NiceGUI were rejected as the opposite of the goal: heavyweight dependency trees and a second server runtime that would replace the working FastAPI serving layer; `htpy` was rejected as swapping one dependency for another. Trade-off: we now hand-escape rather than rely on autoescaping, mitigated by funnelling all interpolation through `_esc` and the regression test.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Collapse `triage/web/` back into a single `triage/web.py` (supersedes the entry above)
- **Decision:** Reverted the `web/` subpackage to one `triage/web.py` module holding the `APIRouter`, the `FILTERS`/`_label_counts` view helpers, and the `Jinja2Templates` instance; templates moved back to `triage/templates/`. `main.py` is unchanged (`from .web import router`). Tests patch `triage.web.get_recent_edits`.
- **Alternatives:** Keep the three-file `web/` subpackage (prior decision); inline everything back into `main.py`.
- **Rationale / trade-offs:** The subpackage was over-engineering for a feature-complete 3-route webapp — three files and a `presentation.py`/`routes.py` split bought separation that a single cohesive module already provides at this size. A single `web.py` still gives the domain/data/web/compose layering (the win we wanted) with far less ceremony. This is the lighter option originally recommended before the subpackage was chosen; reverted on review. Trade-off: the framework-free `presentation` split is gone, but the view helpers are trivial and tested via the routes.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Recent-window read, filter/sort in the app
- **Decision:** `get_recent_edits()` runs one parameterized `SELECT ... ORDER BY event_ts DESC LIMIT 200`; the existing pure `select_edits()` / `_label_counts()` then filter and sort that window in Python.
- **Alternatives:** Push label filter + confidence sort into SQL (per-request `WHERE`/`ORDER BY`); paginate; return the whole table.
- **Rationale / trade-offs:** Keeps SQL trivial and reuses already-tested pure helpers, bounding dashboard cost on a table the firehose will grow. Label counts stay correct because they're computed over the same fetched window. Trade-off: filtering in app means we always fetch the recent window regardless of filter; fine at a 200-row window, and easily pushed into SQL later if the window grows.
- **Made by:** Agent
- **Date:** 2026-06-07

## Phase 4 — Connect ingest + transform

### Connect-only ingest; broker + Console deferred
- **Decision:** Phase 4 adds only a standalone `connect` service (pinned `redpandadata/connect:4.95.0`) reading SSE → transform → `stdout`. The Redpanda broker and Console are deferred to the sink phase (Phase 7), when a topic actually exists to produce to / browse.
- **Alternatives:** Stand up `redpanda` + `console` now (original TODO); add the broker immediately as the sink.
- **Rationale / trade-offs:** Connect runs fine standalone, so adding a broker with nothing consuming it (and a Console to browse an empty cluster) would be premature services and startup-ordering surface for zero Phase-4 value. Defers complexity to the moment it's used, keeping the phase verifiable via `docker compose logs connect`. Trade-off: the broker story lands later, but it lands when it's actually exercised.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Dedup via Postgres UPSERT, not an in-pipeline Connect cache
- **Decision:** Rely on the Postgres `rev_id` primary key + `ON CONFLICT DO UPDATE` (Phase 7) as the sole, durable dedup. No `cache_resources`/`dedupe` processor in Connect.
- **Alternatives:** In-memory `memory` cache with TTL (ephemeral, originally planned); persistent cache (`file`/`redis`); a compacted topic keyed by `rev_id`.
- **Rationale / trade-offs:** A Connect `memory` cache is an ephemeral, per-process hashtable that needs TTL tuning and loses state on restart; a persistent cache or compacted topic would re-implement the exact last-write-wins-by-key guarantee the Postgres PK/UPSERT already provides (and Postgres is already our store). On an SSE stream the same `rev_id` rarely re-arrives — reconnect replays are precisely what the UPSERT absorbs. A Connect cache earns its place for *poll-based* sources (HN/GitHub) that refetch the same ids every poll, to avoid wasted LLM calls; that's the trigger to add it.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### SSE handling, filter scope, and numeric/timestamp coercion (Bloblang)
- **Decision:** Consume SSE via `http_client` (`stream.enabled` + `lines` scanner, `omit_empty`); keep only `data:` frames and `parse_json().catch(deleted())` to fail closed on heartbeats. Filter to `type=edit`, `bot=false`, `namespace=0`, **and `server_name=en.wikipedia.org`**. Project a clean schema; cast `rev_id`/`size_delta` with `.int64()` and format `event_ts` from the epoch `timestamp` via `ts_format(RFC3339, UTC)` with a `meta.dt` fallback.
- **Alternatives:** Keep all Wikimedia projects (no `server_name` filter); leave `rev_id` as a float; use `meta.dt` directly without demonstrating the epoch→ISO conversion.
- **Rationale / trade-offs:** The recentchange firehose is *all* projects; validating live showed it dominated by Wikidata `Q`-item / `wbsetclaim` edits and many non-English wikis, which are meaningless to a `vandalism|substantive|trivia` classifier — scoping to English Wikipedia is "filter before the model / data sense" and keeps later LLM volume bounded and relevant. The `.int64()` casts fix a real bug found in validation: JSON numbers are float64, so `.string()` rendered `rev_id` in scientific notation (`diff=1.35e+09`), breaking diff URLs. Formatting the epoch demonstrates the documented TIMESTAMPTZ gotcha while `meta.dt` is the safety net. Trade-off: English-only narrows the demo to one wiki by design (multi-wiki is out of scope).
- **Made by:** Agent
- **Date:** 2026-06-07

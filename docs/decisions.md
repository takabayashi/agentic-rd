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

## Phase 5 — LLM pass-1 classification (Ollama)

### Containerized Ollama + one-shot model pull gating Connect
- **Decision:** Run Ollama as its own compose service (pinned `ollama/ollama:0.30.6`) with a persistent `ollama` volume, plus a one-shot `ollama-pull` job that preloads `OLLAMA_MODEL`; `connect` waits on it via `depends_on: { condition: service_completed_successfully }`. `OLLAMA_ADDRESS`/`OLLAMA_MODEL` are env-configurable.
- **Alternatives:** Let Connect's `ollama_chat` start/manage its own embedded Ollama (no `server_address`); run Ollama natively on the host and point Connect at `host.docker.internal`; pull the model lazily on first request.
- **Rationale / trade-offs:** A dedicated service keeps the model cache in a named volume (no re-download across restarts) and a separate pull job means the model is guaranteed resident before Connect's first call — closing the cold-start "model not found" race the acceptance criteria call out, without Connect managing a model lifecycle. The env-configurable `OLLAMA_ADDRESS` doubles as the macOS escape hatch (host Ollama for GPU) while the default preserves one-command `docker compose up`. Trade-off: containerized Ollama is CPU-only under Docker Desktop on macOS (slower); accepted because the default must be self-contained, and the host override is documented.
- **Made by:** Agent
- **Date:** 2026-06-07

### Model: `llama3.2` (small, local, configurable)
- **Decision:** Default to `llama3.2` (~3B / ~2 GB) as the classification model.
- **Alternatives:** Larger local models (`llama3.1:8b`, `qwen2`), tiny models (`phi3`, `gemma2:2b`), or a hosted API.
- **Rationale / trade-offs:** A small instruct model is enough for a 4-way label + confidence on short title/comment inputs, keeps the first-run pull and per-edit latency bounded (matters most on CPU-only macOS), and stays fully local (no data leaves the host, no keys). Fully swappable via `OLLAMA_MODEL`. Trade-off: a small model is more likely to drift outside the enum or mis-rank confidence — mitigated by the robust parse + enum normalization and the Phase 6 escalation pass.
- **Made by:** Agent
- **Date:** 2026-06-07

### Keep containerized Ollama as default; host-Ollama override for arm64 Colima (+ `extra_hosts`)
- **Decision:** Keep the in-container `ollama` service as the `docker compose up` default, and make the host-Ollama escape hatch first-class: the `connect` service maps `host.docker.internal:host-gateway` so setting `OLLAMA_ADDRESS=http://host.docker.internal:11434` routes classification to a host-native Ollama.
- **Alternatives:** Make host-Ollama the default (drop the container); pin an older Ollama image; force the container CPU path (`OLLAMA_VULKAN=false`).
- **Rationale / trade-offs:** Live validation surfaced that the `ollama/ollama` image crashes during inference on this host's arm64 Colima VM — `0.30.6` dies with `fatal error: found bad pointer in Go heap (cgo)` and `0.24.0` with `runtime: out of memory` despite ~7.5 GiB free — a Virtualization.framework/cgo incompatibility, not a pipeline bug. The pipeline was validated end-to-end against host-native Ollama (~4.5 s/inference) and the robust parse against crafted dirty/out-of-enum/clamp inputs. The containerized default is still correct for the brief's "one command" on platforms where it works (Docker Desktop, Linux CI); making host-Ollama the default would break self-containment there. Pinning an older image was rejected (both tested versions crash here) and forcing the CPU path didn't help; `extra_hosts` makes the documented override work uniformly (including Linux, where `host.docker.internal` isn't automatic) at zero cost.
- **Made by:** Agent
- **Date:** 2026-06-07

### Robust parse: `re_find_all` first-`{...}` + enum normalization (not trusting `response_format: json`)
- **Decision:** In the `branch` `result_map`, extract the first `{...}` block with `re_find_all("(?s)\{.*\}").index(0).or("{}")`, `parse_json().catch({})`, normalize `label` with `.string().trim().lowercase()` against the fixed enum (unknown/empty → `unclear`), and coerce `confidence` to a number clamped to `[0,1]`. Pass-1 keeps the temporary `stdout` sink. Prompt input is built in `request_map` (title + comment + `size_delta`) and grafted back without overwriting the record.
- **Alternatives:** Trust `ollama_chat`'s `response_format: json` and `parse_json()` the whole reply directly; retry the model on bad output; raise/drop on parse failure.
- **Rationale / trade-offs:** Even with JSON mode, small models leak prose, code fences, or extra keys, so extracting the first object + defaulting is what actually satisfies the "dirty JSON still parses / malformed defaults to `unclear` without crashing" criteria. Enum normalization makes label drift safe and doubles as the prompt-injection guardrail (output can only ever be one of four values). Confidence coercion/clamp guarantees `[0,1]` for the DB CHECK and the dashboard sort. We chose fallback-to-`unclear` over an in-pipeline retry loop (latency/cost on a firehose; later UPSERT correction is cheaper) — the broader retry decision is recorded again in Phase 6/7. Note: `re_find` does not exist in Bloblang (caught by `connect lint`); `re_find_all(...).index(0)` is the supported form.
- **Made by:** Agent
- **Date:** 2026-06-07

### Default model: `qwen2.5:1.5b` (supersedes the `llama3.2` entry above)
- **Decision:** Change the default `OLLAMA_MODEL` from `llama3.2` (~2 GB) to `qwen2.5:1.5b` (~1 GB, Apache-2.0). Still fully swappable via `OLLAMA_MODEL`.
- **Alternatives:** Keep `llama3.2`; go even smaller (`qwen2.5:0.5b`, ~0.4 GB); bake the model into a custom image to skip `ollama-pull` (rejected — moves the same download to build/registry, balloons image size, and re-introduces the publish pipeline we cut); switch engines (llama.cpp/vLLM — same weights/memory, doesn't help).
- **Rationale / trade-offs:** A ~1 GB model roughly halves the RAM footprint and first-run pull versus `llama3.2`, fitting a small Docker VM (~2–3 GB) so a constrained `docker compose up` doesn't OOM on first inference — directly addressing the memory blocker hit on a 1.9 GiB Colima VM. Qwen2.5 1.5B is a capable instruct model for a 4-way label + confidence on short title/comment text, and its Apache-2.0 license is clean (unlike Llama terms) if the image is ever redistributed. Kept the simple `ollama-pull` + cached volume (download once on first `up`) over baking, per the "plain but works / least complexity" direction. Trade-off: a smaller model drifts a bit more, still mitigated by the robust enum-normalize parse and the Phase 6 escalation pass.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Revert default to `llama3.2`; `qwen2.5` is the low-memory fallback (supersedes the entry above)
- **Decision:** Default `OLLAMA_MODEL` back to `llama3.2` (~2 GB). Keep `qwen2.5:1.5b`/`0.5b` documented as a low-memory fallback in `.env.example`/README, not the default.
- **Alternatives:** Keep `qwen2.5:1.5b` default; A/B a mid model (`qwen2.5:3b`); prompt-tune the small model.
- **Rationale / trade-offs:** Two things changed the calculus. (1) The whole `docker compose up` was validated on **Docker Desktop** (~18 GB VM, container Ollama healthy with 0 restarts — the crash was Colima-VZ-specific), so the 1.9 GiB constraint that motivated the tiny model no longer applies on the actual run environment. (2) Live end-to-end testing showed `qwen2.5:1.5b` labels ~85% of real edits `vandalism` at 0.96–1.00 confidence — including obvious good edits (category moves, adding refs, cleanup); because the errors are *high-confidence*, the Phase 6 escalation (low-confidence trigger) can't correct them, making the triage output unusable. `llama3.2` classified sensibly in Phase 5. Trade-off: `llama3.2` needs ~4 GB VM and carries the Llama license vs Qwen's Apache-2.0 — acceptable since it's run locally, not redistributed, and the small models remain a documented escape hatch for constrained VMs.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

## Phase 6 — Confidence-based escalation (the multi-step loop)

### Fetch the real diff for every edit (MediaWiki compare API) as the classification evidence
- **Decision:** Before classifying, enrich every surviving edit with its actual diff via a Connect `branch` calling the MediaWiki REST compare API (`/w/rest.php/v1/revision/{from}/compare/{to}`, keyed off the event's `revision.old`/`revision.new`); keep only the changed lines (`+`/`-`/`~`, context dropped), truncate to ~4 KB, and stash it in **metadata** (not the clean root). The fetch fails **closed** (`.catch("")`) and is throttled by a `local` `wiki_api` rate limit (10/s).
- **Alternatives:** Classify on SSE metadata only (title/comment/size_delta — no diff); fetch the diff *only* on escalation (diff-on-escalation); persist the diff in the record/DB.
- **Rationale / trade-offs:** The recentchange event is only edit *metadata* and never the changed text, so metadata-only classification is guessing for the ambiguous cases (empty/cryptic comment, named user, small delta) — exactly the ones that matter. The diff is the only genuinely new evidence, so we fetch it for *every* survivor and let pass-1 reason over real content (human chose this over diff-on-escalation for max per-edit accuracy). Storing it in metadata keeps the projected root exactly DB-ready (no diff leaks into the schema or stdout) and means Phase 7's `sql_insert` needs no change. Fail-closed + rate limit keep a transient API hiccup or politeness limit from stalling/crashing the firehose. Trade-off: one outbound HTTP call per surviving edit (latency + Wikipedia API load) — bounded by the pre-model filter and the rate limit, with 429s/rate caps under sustained high volume as the documented production failure mode (observed live: REST compare returns 429, fails closed to an empty diff, classification continues).
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Confidence `switch` escalation as a second re-prompt pass
- **Decision:** After pass-1, a `switch` checks `this.confidence < ${CONFIDENCE_THRESHOLD:0.7} || this.label == "unclear"` and routes matches into a second `branch` that re-classifies with a more rigorous per-label rubric, the editor identity, and the first-pass `{label, confidence}` for self-critique (re-reading the same diff), then stamps `escalated = true`. `escalated` defaults to `false` in projection so confident rows skip the 2nd model call. `CONFIDENCE_THRESHOLD` is config-interpolated (Connect substitutes `${VAR:default}` before parse), so it's env-configurable with a `0.7` default.
- **Alternatives:** One classification call (no escalation); escalate by fetching *more* diff context (moot now that pass-1 already has the full diff); a fixed always-two-passes design.
- **Rationale / trade-offs:** Satisfies the brief's "more than one prompt / confidence-based branching" with a real cost lever — only ambiguous edits pay the second model call, and the threshold visibly trades escalation volume against coverage. Since pass-1 already has the diff, escalation adds *better reasoning* (rubric + reflection + editor signal), not new evidence. The `switch` doubles as the brief's "route" requirement (route ambiguous items to escalation) alongside the single labeled topic in Phase 7. Trade-off: the escalation prompt re-reads the same diff, so its lift is judgment, not facts; acceptable because the diff fetch (above) supplies the missing evidence for both passes.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Retries-on-bad-output: fallback-to-`unclear` + UPSERT, not an in-pipeline loop (restated for pass 2)
- **Decision:** Keep the Phase 5 stance for both passes: malformed/empty model replies normalize to `unclear` via the identical robust parse (first `{...}` extract + enum-normalize + `[0,1]` clamp) rather than retrying the model inline. A later, more confident pass corrects the row through the Postgres `rev_id` UPSERT (Phase 7).
- **Alternatives:** In-pipeline retry loop on bad output (e.g. a `retry` processor around the `branch`); raise/drop on parse failure.
- **Rationale / trade-offs:** On a ~50/sec firehose, blocking a synchronous model call to retry adds latency and cost for marginal gain, while a cheap default plus a self-correcting later pass keeps throughput bounded and converges. Reused verbatim in pass 2 so both passes are crash-safe, enum-constrained, and advisory-only (the prompt-injection guardrail). Would flip toward explicit retries if classifications were authoritative/irreversible.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Fail-safe default + set `escalated` inside result_map (Bloblang root-rebuild gotcha)
- **Decision:** Add a `mapping` after pass-1 that starts with `root = this` and defaults a missing/non-enum `label` to `unclear` and a missing/non-numeric `confidence` to `0`. Set `escalated = true` *inside* the escalation `branch.result_map` (alongside label/confidence) rather than in a trailing standalone `- mapping: root.escalated = true`.
- **Alternatives:** Null-guard only inside the switch `check`; the trailing standalone mapping we first wrote.
- **Rationale / trade-offs:** When the pass-1 `branch`'s `ollama_chat` call fails (model unreachable/errored — e.g. pointing at a crash-looping containerized Ollama), Connect skips `result_map`, so the record reached the escalation `switch` with no `label`/`confidence` — emitting blank rows and crashing the `switch` on `null < threshold` (observed live as 328 `cannot compare types null` errors, 0/303 rows labelled). The fail-safe defaults such rows to `unclear`/0, realizing the PRD's "transient LLM failure → land as `unclear`, corrected by a later UPSERT" and keeping the firehose crash-free; it is idempotent for already-classified rows. Separately, a standalone Bloblang `mapping` rebuilds `root` from scratch, so a partial `root.escalated = true` dropped every other field (wiped escalated rows to `{"escalated":true}` in testing — the exact gotcha the brief calls out). `branch.result_map` inverts that rule (it grafts partial assignments back), so `escalated` belongs there; the fail-safe mapping uses `root = this` for the same reason.
- **Made by:** Agent
- **Date:** 2026-06-07

### `ollama-pull` also needs `extra_hosts` for the host-Ollama override
- **Decision:** Add `host.docker.internal:host-gateway` to the `ollama-pull` service (it already exists on `connect`), so `OLLAMA_ADDRESS=http://host.docker.internal:11434` works for the model-pull job too.
- **Alternatives:** Only map it on `connect` (prior state); skip the pull job when using a host Ollama.
- **Rationale / trade-offs:** With the host override, `ollama-pull` sets `OLLAMA_HOST=http://host.docker.internal:11434` but, lacking the host mapping, couldn't resolve the name (`could not connect to ollama server`), failed `exit 1`, and — because `connect` gates on `service_completed_successfully` — blocked the whole pipeline. The Phase 5 host-override decision mapped only `connect`; this completes it so the documented one-command host path actually starts end-to-end on Colima/Linux (where `host.docker.internal` isn't automatic). Harmless on the in-container default (the mapping is simply unused).
- **Made by:** Agent
- **Date:** 2026-06-07

### Developer Makefile for the compose + test loop
- **Decision:** Add a root `Makefile` wrapping the recurring workflow: service control (`up`/`down`/`down-v`/`restart`/`restart-connect [THRESHOLD=]`/`restart-webapp`/`ps`/`build`), pipeline observability (`logs-connect`/`diffs`/`labels`/`escalations`/`errors`/`psql`/`ollama-check`), and quality (`install`/`test`/`lint`/`fmt`/`yamllint`/`connect-lint`/`check`). `check` mirrors CI minus build/gitleaks.
- **Alternatives:** Shell scripts under `scripts/`; document raw commands only; a task runner (`just`/`task`).
- **Rationale / trade-offs:** A Makefile is ubiquitous (no extra install), self-documents via `make help`, and captures the exact error-prone commands (esp. `restart-connect THRESHOLD=…` and the log-grep helpers) surfaced while debugging Phase 6. Pure convenience — no runtime surface; the underlying `docker compose`/`pytest`/`ruff` paths still work directly.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

## Phase 7 — Dual sink end-to-end + connector hardening (planning)

### Model audit log as a full Redpanda topic (not a Postgres table or logs)
- **Decision:** Plan a dedicated **append-only** `model.audit` topic as a second fan-out output capturing one record per edit with both passes' raw model I/O (`{rev_id, model, ts, pass1{input, raw_response, label, confidence}, pass2|null}`); short **time-based retention**, **not compacted**, keyed by `rev_id`. Capture each pass's input/raw response in metadata during its `branch`, reshape in the audit output's `processors`. Defer any sync to a `model_calls` table to later.
- **Alternatives:** Structured `log` lines only (cheapest, no infra); a `model_calls` Postgres audit table (queryable, reuses the DB); one-record-per-call (vs per-edit-with-nested-passes); a compacted/keyed-LWW topic (rejected — collapses history).
- **Rationale / trade-offs:** The brief's storage is already a stream + DB, and an audit *stream* fits replay / prompt-eval / drift-inspection and the "explain why this label" story better than rows; the human chose it explicitly and is fine syncing to a table later (a Kafka→Postgres sink is trivial to add). Append-only + time-retention is correct because every call is a distinct event (unlike the LWW-by-`rev_id` classified topic). Per-edit-with-nested-passes keeps escalation linked to its pass-1 in one message and avoids splitting into two. Marked an **Extension** (beyond the brief's asked scope) so it doesn't bloat the core ingest→reason→serve path. Caveats: stores full prompts + raw responses incl. the (capped) diff — volume/retention matters, and the prompts hold untrusted title/comment/diff (advisory, local-only).
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Producer-side `zstd` compression on the topic outputs
- **Decision:** Compress both `wiki.edits.classified` and `model.audit` outputs with `zstd`, paired with the output batching from connector hardening.
- **Alternatives:** `lz4`/`snappy` (faster, weaker ratio), `gzip` (slower), no compression.
- **Rationale / trade-offs:** The payloads are text JSON + wikitext diffs, which compress ~5-10x; at post-filter throughput (~1-5 edits/sec, doubled by escalation) CPU isn't the bottleneck, so we optimize for ratio with `zstd`. Compression operates per-batch, so it synergizes with the planned batching (bigger batches → better ratio) and directly offsets the audit topic's volume/retention cost. It is transparent to consumers and Console (standard Kafka batch compression). Trade-off: a little producer CPU; tiny batches compress less (fine at this steady, modest volume).
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### (Implemented) Broker = Redpanda dev-container; `redpanda` output + Console; explicit topic creation
- **Decision:** Add `redpanda` (single-node `--mode dev-container`), `console` (host `:8090`), and a one-shot `redpanda-topics` job that `rpk topic create`s both topics with explicit configs (`wiki.edits.classified` `cleanup.policy=compact`; `model.audit` `cleanup.policy=delete` + `retention.ms=6h`). Connect produces via its native `redpanda` output and gates on the broker healthy + topics created.
- **Alternatives:** `kafka`/`kafka_franz` outputs; rely on `allow_auto_topic_creation` (default true) instead of an init job; skip Console.
- **Rationale / trade-offs:** The `redpanda` output is the current franz-go-based client (vs the legacy `kafka`). Explicit creation lets us set compaction/retention deliberately — auto-create would give default (delete) policy, losing the compacted-by-`rev_id` semantics that mirror the UPSERT. Console satisfies the brief's "somewhere we can see it" and makes the topics browsable; it maps to `:8090` to avoid the dashboard's `:8080`. Pinned tags (`redpanda:v25.3.15`, `console:v3.7.4`) per the repo's pinned-image rule.
- **Made by:** Agent
- **Date:** 2026-06-08

### (Implemented) Dual sink via broker `fan_out`: `redpanda` topic + `sql_raw` UPSERT (wrapped in `retry`)
- **Decision:** Replace the stdout sink with an `output.broker` `fan_out` to: (1) `wiki.edits.classified` (`redpanda`, key `rev_id`), (2) Postgres via `sql_raw` `INSERT ... ON CONFLICT (rev_id) DO UPDATE` wrapped in a `retry` output, and (3) the `model.audit` topic. `classified_at = now()` is stamped on write.
- **Alternatives:** App-side consumer reading the topic and writing Postgres itself (vs Connect as the sink); `sql_insert` (no upsert); no `retry` wrapper; `fan_out_sequential`.
- **Rationale / trade-offs:** Connect as the sink keeps everything in one config with no extra service to run — and directly feeds the brief's "Connect as the sink vs app-side writes" tradeoff. UPSERT requires `sql_raw` (the `sql_insert` output has no `ON CONFLICT`). Wrapping the SQL output in `retry` isolates transient Postgres downtime so it's retried, not fatal. Known `fan_out` caveat: if one output fails, the message is retried to *all* outputs, which can re-produce to Kafka — acceptable here because the classified topic is compacted by `rev_id` and the Postgres UPSERT is idempotent, so duplicates converge.
- **Made by:** Agent
- **Date:** 2026-06-08

### (Implemented) Cap redpanda memory; Docker Desktop is the reference runtime
- **Decision:** Start redpanda with `--memory=1G --reserve-memory=0M`, and document that the full stack needs a Docker VM with **≥ 4 GB**; Docker Desktop is the reference environment. On Apple Silicon, run Ollama on the host.
- **Alternatives:** No memory cap (let dev-container auto-size to the VM); require a bumped Colima VM (`colima start --memory 6`); make host-Ollama the default.
- **Rationale / trade-offs:** A ~1.9 GiB Colima VM **OOM-killed** redpanda (`ExitCode=137 OOMKilled=true`, crash-looping) — confirmed via `docker inspect`. Capping `--memory` makes redpanda a predictable citizen and protects smaller VMs, but it doesn't conjure RAM, so the real requirement is a ≥4 GB VM — which Docker Desktop provides by default (the whole stack was validated there). This also lines up with the Phase 5 finding that the containerized Ollama crashes under Colima's Virtualization.framework, so host Ollama remains the Mac path. Trade-off: Docker Desktop has licensing terms vs Colima's FOSS; both work, Colima just needs the memory bump + host Ollama.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Dashboard UX for easier testing: freshness stats, escalated filter, article + diff links
- **Decision:** Enrich the dashboard with a header stat line (total / escalated count / newest "N ago"), a per-row "Classified" relative-time column, an **escalated** filter chip combinable with the label chips (and `/api/edits?escalated=1`), separate **article** and **diff** links per row, and the `#rev_id`. No `EditView`/API-shape change — the article URL is derived in the renderer and `select_edits` gains an `escalated_only` flag.
- **Alternatives:** Keep the minimal table; add a sort toggle (deferred); store the diff text on the row / fetch it on demand to show the changed text inline.
- **Rationale / trade-offs:** Surfaces pipeline liveness, escalation behaviour, and enough per-edit context (links + rev id) to evaluate misclassifications without dropping to `psql`/`rpk` — directly the "make testing easier" ask. Keeping the API shape stable means existing tests/contract are untouched. The actual diff *text* stays in the `model.audit` topic (not Postgres); the diff link opens it on Wikipedia, and inline diff text is deferred as a heavier follow-up. Trade-off: a couple more columns on the table.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

## Phase 8 — Focused automated tests

### Python reference parse module + DB-free pytest (no Connect harness)
- **Decision:** Add `app/triage/pipeline_parse.py` mirroring ingest SSE + classify `result_map` Bloblang; cover edge cases in `test_pipeline_parse.py`. Extend dashboard/repository tests (escalated filter, parameterized `LIMIT %s`, 503/empty/XSS). Add a `connect-lint` CI job; document coverage in README "Testing".
- **Alternatives:** Full Redpanda Connect test harness for every Bloblang mapping; integration tests against live Postgres/broker in CI.
- **Rationale / trade-offs:** The brief caps scope at "plain but works" — the highest-risk logic (dirty model JSON, enum drift, heartbeat fail-closed, SQL parameterization, XSS) is pure and testable in Python without spinning infra. Connect stays runtime source of truth; the Python module is a tested reference to prevent drift. Trade-off: two places to update if parse rules change (acceptable while rules are stable).
- **Made by:** Agent
- **Date:** 2026-06-08

### Drop `pipeline_parse.py` — Connect YAML is the sole parse source of truth
- **Decision:** Remove `app/triage/pipeline_parse.py` and `test_pipeline_parse.py`. Keep dashboard/repository pytest + `connect-lint` CI + e2e for pipeline parse rules.
- **Alternatives:** Keep the Python mirror; inline test helpers only; full Connect test corpus.
- **Rationale / trade-offs:** The module was never used at runtime — only tests imported it — so it duplicated Bloblang with real drift risk and no product benefit. App tests should guard the app; Connect lint + live pipeline guard ingest/classify. Supersedes the "Python reference parse module" entry above.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

## Phase 10 — Staged Connect pipeline (topics as protocol)

### Split monolith into three Connect services on compacted topics
- **Decision:** Replace the single `connect/wikipedia.yaml` with three pipelines — `connect/ingest.yaml` (SSE → `wiki.edits.raw`), `connect/enrich.yaml` (`wiki.edits.raw` → diff fetch → `wiki.edits.enriched`), `connect/classify.yaml` (`wiki.edits.enriched` → Ollama pass-1 + escalation + fan-out sink). Topics are the inter-stage protocol; keys are `rev_id`; raw/enriched/classified topics use `cleanup.policy=compact`. The classify stage remains the Connect-based agent (option A — no separate Python classifier).
- **Alternatives:** Keep one monolithic Connect job; two-service split (ingest+enrich / classify); Python agent consuming `wiki.edits.enriched`; in-pipeline `dedupe` cache before LLM.
- **Rationale / trade-offs:** Stages map cleanly to connector vs agent responsibilities and make the data path visible in Console (`raw` → `enriched` → `classified`). Handoff fields (`parent_rev`, `diff`) live in the **JSON payload**, not metadata — Kafka round-trips drop metadata. Classify strips `diff`/`parent_rev`/`schema_version` before Postgres/topic sink so the DB schema is unchanged. At-least-once delivery + compacted keys + UPSERT still converge duplicates. Trade-off: three containers and two extra Kafka hops vs one config; accepted for clarity and replay (reconsume `wiki.edits.enriched` after prompt changes without re-hitting Wikipedia).
- **Made by:** Human+Agent
- **Date:** 2026-06-08

## Phase 11 — One-command start + arch/maintainability hardening

> This phase intentionally exceeds the original "couple-of-hours / plain but
> works" cap (the human asked for "everything in both tiers"). Several items
> reverse earlier scope cuts (Alembic, metrics, richer UI); each is noted as
> superseding where relevant.

### One-command start (`start.sh` + `install.sh` + `make start`)
- **Decision:** Add a self-healing bootstrap `start.sh` (preflight Docker checks, seed `.env`, generate a random `POSTGRES_PASSWORD`, auto-detect host Ollama on Apple Silicon, `docker compose up -d`, wait-for-`/healthz`, open the dashboard) plus a `curl | bash` `install.sh` that clones then runs it, and a `make start` target. WarpStream-demo style.
- **Alternatives:** Document `docker compose up` only; a Python launcher; a Taskfile.
- **Rationale / trade-offs:** `docker compose up` already worked, but a wrapper removes the common first-run papercuts (Docker not running, missing `.env`, arm64 Ollama crash, "is it up yet?"). Bash keeps it dependency-free and inspectable. Trade-off: a shell script to maintain; mitigated by `bash -n` syntax checks and keeping logic small. `curl | bash` is convenience for fresh machines (the user explicitly asked); it clones over HTTPS and runs only repo code.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Align the Python version to 3.12.13 across image/CI/ruff
- **Decision:** Pin `app/Dockerfile` to `python:3.12.13-slim` and CI `setup-python` to `3.12.13`, matching ruff's `target-version = py312` and the documented decision. Fix the contradicting Dockerfile comment.
- **Alternatives:** Align everything up to 3.14; leave the drift.
- **Rationale / trade-offs:** The image had drifted to `3.14.5-slim` while CI/lint/tests targeted 3.12 — so the shipped runtime was never linted or tested. One version end-to-end means tests exercise what ships. Chose 3.12.13 (down, not up) to match the existing decision/CI with zero behavioral risk.
- **Made by:** Agent
- **Date:** 2026-06-08

### Shared Bloblang library for the classify parse/enum (`connect/lib/classification.blobl`)
- **Decision:** Extract the robust LLM-reply parse, enum-normalize, and confidence-clamp into reusable Bloblang `map`s, imported by both the pass-1 and pass-2 `result_map`s (and the fail-safe mapping). The label enum lives once, in `normalize_label`.
- **Alternatives:** Keep the ~6-line parse duplicated in both passes (prior state); a resources file of `processor_resources`; YAML anchors.
- **Rationale / trade-offs:** The two passes had near-identical parse blocks and the enum literal appeared 4×, the biggest drift risk in the pipeline. A shared `map` + `apply` is the idiomatic Bloblang DRY and keeps the two passes provably identical. The `redpanda` output / `logger` blocks were left per-file deliberately (they differ by topic; extracting them adds indirection without removing real duplication — per the architecture-principles "don't over-engineer" rule). Trade-off: an imported file must be mounted into the container and resolved by `connect lint` (the Makefile/CI now mount the whole `connect/` dir). **Validation caveat:** Connect changes were authored without a local Docker to run `connect lint`/e2e — they must pass `make connect-lint` + `make connect-test` before being trusted.
- **Made by:** Agent
- **Date:** 2026-06-08

### Typed config via pydantic-settings; lazy single-pool repository
- **Decision:** Add `triage/config.py` (`Settings` + cached `get_settings()`) as the one place env is read; refactor `repository.py` to build a single pool lazily via `_get_pool()` (dropping the `_opened` global flag) and add `check_ready()`.
- **Alternatives:** Keep scattered `os.getenv`; a global pool opened at import.
- **Rationale / trade-offs:** Centralized, validated config fails fast on bad input and makes new tunables (`RECENT_WINDOW_LIMIT`) first-class. The lazy pool removes mutable module state that tests had to patch, and `check_ready()` backs `/readyz`. Trade-off: one more module + a settings dependency (small, already implied by FastAPI's pydantic).
- **Made by:** Agent
- **Date:** 2026-06-08

### Observability: Prometheus metrics + JSON logging + `/readyz`
- **Decision:** Add a `/metrics` endpoint + ASGI middleware (request count/latency) and one-line JSON app logging; enable `metrics: { prometheus: {} }` on all three Connect services (classify's `:4195` mapped to host); add a DB-backed `/readyz` distinct from liveness `/healthz`.
- **Alternatives:** Logs-only (prior state); full OpenTelemetry tracing + a Prometheus/Grafana stack in compose.
- **Rationale / trade-offs:** Metrics + structured logs + readiness are the high-value, low-weight observability primitives a real operator needs, and they're scrapeable by any external Prometheus without bundling a stack. Full OTel tracing was judged disproportionate for a single-table app + 3-stage pipeline and was left as a documented next step. Supersedes the Phase-era "observability stack: out of scope" stance for these primitives.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Live-feed poller replaces the full-page meta-refresh
- **Decision:** Render the dynamic dashboard region as a server-rendered `#feed` fragment (`GET /fragment/edits`) and add a tiny vanilla-JS poller that swaps it in every few seconds, flashing new rows; add `limit`/`offset` pagination to `/api/edits`. Extract CSS to `styles.py`.
- **Alternatives:** Keep `<meta http-equiv="refresh">`; adopt HTMX (CDN or vendored); a client-side SPA re-rendering from JSON.
- **Rationale / trade-offs:** The full-page reload was jarring and lost scroll/focus. Fetching a server-rendered fragment keeps the server as the single source of markup (no duplicated row rendering, unlike an SPA) and needs no external library or build step (unlike HTMX, which would add a CDN/runtime dependency for a local-only tool). Trade-off: ~25 lines of hand-written JS to maintain.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Alembic migrations as additive forward-evolution (SQLAlchemy schema source)
- **Decision:** Introduce Alembic with a single SQLAlchemy table (`triage/schema.py`) as the schema source and a one-shot `migrate` compose service running `alembic upgrade head` before app/classify. The initial revision uses idempotent `create_all(checkfirst=True)`; `db/init.sql` stays as the first-boot bootstrap. A schema-contract test ties `EditView` ↔ `init.sql` ↔ `triage.schema`.
- **Alternatives:** Keep initdb-only (prior, deferred-Alembic decision); make Alembic the *sole* creator (drop `init.sql`).
- **Rationale / trade-offs:** Real services need forward migrations; this adds them without risking the one-command start, because the initial migration no-ops on an already-bootstrapped volume and only records the baseline. Keeping `init.sql` means two schema artifacts, so the contract test guards drift. Dropping `init.sql` entirely was rejected to avoid changing the zero-tooling first boot and the existing `down -v` re-seed story. Supersedes the Phase-3 "Alembic deferred — overkill" note. **Validation caveat:** the `migrate` service ordering wasn't run here (no Docker); needs a `docker compose up` e2e.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Inter-stage contract + dead-letter topic
- **Decision:** `connect-enrich` validates `schema_version == 1` + present `rev_id` and routes failures to a `wiki.edits.dead_letter` topic (24h retention) via an output `switch`, making `schema_version` load-bearing instead of dead metadata.
- **Alternatives:** Keep silently dropping malformed records; a full schema registry; DLQ at every stage.
- **Rationale / trade-offs:** A DLQ makes malformed handoffs inspectable rather than invisible, and gives `schema_version` a job. Added at the first topic consumer (enrich) where records re-enter from Kafka; classify was left un-DLQ'd because its fail-safe always yields a valid label and it strips `schema_version` before the sink (a DLQ there would add risk for little value). A schema registry was judged too heavy for the take-home. **Validation caveat:** unlinted here (no Docker).
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Env-driven log verbosity + per-message classify visibility
- **Decision:** Parameterize all three Connect stages' `logger.level` via `${CONNECT_LOG_LEVEL:-INFO}` (passed through the shared `connect-env` anchor), add env-gated `OLLAMA_DEBUG=${OLLAMA_DEBUG:-0}` to the `ollama` service, and add two `log` processors to `classify.yaml` — `pass1 classified` (before the escalation switch) and `classified` (after it, with the `escalated` flag) — each emitting structured `rev_id`/`label`/`confidence` fields.
- **Alternatives:** Hardcode `DEBUG` in the YAMLs (not reversible without an edit); rely solely on global `DEBUG` level (firehose, no per-record business context); a sidecar log shipper / dedicated tracing.
- **Rationale / trade-offs:** Operators need to (a) turn up framework verbosity without editing files and (b) see per-edit classification outcomes at the default `INFO` level. Env interpolation matches the existing `${VAR:-default}` pattern and keeps default behavior unchanged. The `log` processors give business-level visibility (label/confidence/escalation per `rev_id`) that a raw log level can't. Trade-off: two extra processors in the hot path (cheap; no IO) and a documented gotcha — Connect reads its bind-mounted config only at startup, so config changes need a container recreate. Verified live: `pass1 classified`/`classified` lines emit with structured fields; `CONNECT_LOG_LEVEL=DEBUG` and `OLLAMA_DEBUG=1` override correctly while defaults stay `INFO`/`0`.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Scalable classify metrics port (target-only mapping)
- **Decision:** Change `connect-classify`'s metrics port from the fixed `"4195:4195"` host mapping to target-only `"4195"`, so Docker assigns a random host port per replica and `docker compose scale connect-classify=N` works without `port is already allocated` conflicts.
- **Alternatives:** Keep the fixed `4195:4195` and never scale the service; drop host publishing entirely and scrape `4195` over the internal Docker network via DNS.
- **Rationale / trade-offs:** Target-only publishing is the minimal change that unblocks horizontal scaling of the classify stage (the LLM-bound bottleneck) while still exposing each replica's metrics on the host for ad-hoc inspection. Trade-off: the host port is no longer stable at `4195`, so a host-targeted Prometheus scrape needs service discovery (or the internal-network approach) instead of a hardcoded port — noted as a follow-up. Verified locally: two replicas came up on distinct ephemeral host ports (`61513`, `61514`).
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Tests against real infra: testcontainers Postgres + Connect Bloblang harness
- **Decision:** Add a testcontainers Postgres integration test (real psycopg/SQL/pool, skips when Docker is absent) and a Redpanda Connect unit-test harness (`connect/tests/`, `make connect-test`) exercising the shared parse library; wire both into CI.
- **Alternatives:** Stay DB-free + lint-only (prior decision); a Python mirror of the Bloblang (explicitly rejected before for drift).
- **Rationale / trade-offs:** The integration test covers the SQL/pool path the unit tests mock; the Connect harness tests the *actual* Bloblang library (no Python mirror, so no drift) — the gnarly parse/normalize/clamp cases that were previously only covered by live e2e. Supersedes the "drop pipeline_parse.py / lint+e2e only" stance for the parse logic.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### `start.sh` hardening: build-on-start + volume-aware password (found via debugging)
- **Decision:** `start.sh` now runs `docker compose up -d --build` (was `up -d`), and `ensure_db_password` only generates/bakes a `POSTGRES_PASSWORD` when **no `pgdata` volume exists yet** — otherwise it leaves the credential untouched and warns to `down -v` if auth fails.
- **Alternatives:** Keep `up -d` (no build) and unconditional password generation; drop the generated password entirely; detect dependency changes some other way.
- **Rationale / trade-offs:** Live runs surfaced two real failures. (1) `migrate` died with `exec: "alembic" not found` because `up -d` reused a cached image built before `alembic` was added to `requirements.txt`; `--build` makes a dependency change always land in the image (cheap when layers are cached). (2) `migrate` then died with `password authentication failed for user "wiki"` because the generator wrote a new `POSTGRES_PASSWORD` into `.env` while the existing `pgdata` volume still held the old `change-me` — Postgres only applies `POSTGRES_PASSWORD` on first init of an empty volume. Gating generation on volume absence removes that footgun while keeping the fresh-install security win. Both were confirmed with container exit codes/logs before fixing; the e2e run that verified the fix also validated the previously-unlinted Connect changes (492 rows in Postgres, all topics advancing, `dead_letter` empty, zero connect errors). **Validation caveat (still open):** `make connect-lint` / `make connect-test` haven't been run, though the live e2e exercised the same configs successfully.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Content gate: skip the model for empty-diff edits (reason column)
- **Decision:** Add a content gate at the top of `connect/classify.yaml`: a `switch` whose first case matches edits with no usable evidence — the **cleaned** diff (`re_replace_all("\\s+", "")`) shorter than `DIFF_MIN_CHARS` (default 1) **and** `|size_delta|` below `BLANKING_MIN_DELTA` (default 100) — and stamps them `label=unclear`, `confidence=0`, `escalated=false`, `reason=empty_diff` with **no** `ollama_chat` call (so no pass-1 *and* no escalation). All other edits run the existing two-pass flow and are stamped `reason=classified`. Added a `reason TEXT NOT NULL DEFAULT 'classified' CHECK (reason IN ('classified','empty_diff'))` column threaded through `db/init.sql`, `triage/schema.py`, `EditView`, the repository SELECT, the SQL-sink UPSERT, `db/seed.sql` (+ one demo `empty_diff` row), and surfaced on the dashboard as a muted "skipped" tag (with a tooltip). Schema is **recreated** (`docker compose down -v`), not migrated — the data is disposable, so no new Alembic revision.
- **Alternatives:** Hard-drop low-content edits at ingest (loses auditability and skews dashboard counts vs. the firehose — rejected, consistent with the existing "fail-closed but visible" dead-letter choice); reuse `unclear`+`confidence=0` without a `reason` column (no schema change, but a gated `unclear` is then indistinguishable from a model `unclear`); keep classifying but only skip the *escalation* pass for thin edits (halves waste with no gate/schema change — a lighter option we passed on because skipping pass-1 too is the bigger win and the `reason` tag is a useful demo); multiple reasons (`too_small`, etc.) — deferred to keep the demo focused on one.
- **Rationale / trade-offs:** Directly removes "dumb" inferences (up to two model calls per content-less edit) while keeping the row visible and self-describing, and correctable later by the `rev_id` UPSERT. The `|size_delta|` exemption is the key nuance: an empty `+/-` diff with a large negative delta is blanking/section-removal — a vandalism signal we must *not* auto-skip — so those still reach the model. Trade-off: one more column to keep in cross-layer sync (covered by `test_schema_contract.py`) and a gate that could in principle skip a genuinely-meaningful tiny edit (mitigated by the low `DIFF_MIN_CHARS` default and the delta guard; tune via env). Validated: ruff + pytest (added `reason` rendering + API tests; contract test covers the new column), `connect-lint`, and a live `down -v && up` showing the seed `empty_diff` row tagged "skipped" on the dashboard and gated edits emitting a `skipped (empty_diff)` log with no model call.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Dev live-reload for the webapp (bind-mount + uvicorn --reload)
- **Decision:** Run the `webapp` compose service with an explicit uvicorn `--reload` command (watching `/app/triage` and `/app/static`) and bind-mount `./app/triage` and `./app/static` over the baked image. Editing dashboard assets or app code is now picked up live (browser refresh), with no `docker compose up --build`. `--reload` needs no new dependency — `watchfiles` already ships with the pinned `uvicorn[standard]`.
- **Alternatives:** Keep rebuild-on-change (status quo — correct but slow to iterate on UI); mount only `app/static` (assets live, Python still needs rebuild); a separate `docker-compose.override.yml` for dev-only mounts (cleaner prod/dev split, but more files and the project favors a single compose file); a host-run uvicorn against the containerized DB (bypasses the image entirely, but diverges from the one-command `docker compose up` flow).
- **Rationale / trade-offs:** Removes the rebuild-and-cache-fight loop that slowed several UI fixes in this session, at the cost of overlaying the image in dev. The baked image (`COPY . ./`) remains the source of truth on a fresh clone and in CI — the mounts only overlay it locally — so reproducibility is unchanged. Trade-offs: `--reload` adds a watcher process (negligible) and the mounted host files shadow the image copy in dev (intended). Verified live: uvicorn logs "Started reloader process using WatchFiles" watching both dirs; a marker appended to `dashboard.css` was served immediately with no rebuild, then reverted.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Dashboard assets as static files (CSS/JS out of Python strings)
- **Decision:** Extract the dashboard CSS and JS into real files under `app/static/` (`dashboard.css`, `dashboard.js`, `warmup.css`), mount them at `/static` via Starlette `StaticFiles` in `main.py`, and link them from the markup with `<link rel="stylesheet">` / `<script src defer>`. Deleted `triage/styles.py` (the `DASHBOARD_CSS`/`WARMUP_CSS` string constants) and the `_POLL_JS` string in `render.py`. The poll interval (still owned in Python) is handed to the static script via a `<body data-refresh-ms>` attribute so the JS stays a plain cacheable asset (no server-side string substitution). Dropped the now-stale `styles.py` per-file `E501` ignore in `ruff.toml`.
- **Alternatives:** Keep CSS/JS inlined as Python strings (status quo — no extra HTTP requests, but the assets aren't cacheable, aren't editable as real CSS/JS, and bloat every HTML response); keep them as `.css`/`.js` files but inline their contents at render time (a middle option — files for editing, but no caching win and the page re-reads them); a full templates/ + bundler setup (overkill for one small page, adds a build step the project deliberately avoids).
- **Rationale / trade-offs:** Real asset files are editable with proper tooling/linting, are browser-cacheable (served once, not re-sent in every page), and keep `render.py` focused on markup. The server still owns all row markup (the JS only swaps server-rendered fragments), so the XSS-safety boundary is unchanged. Trade-offs: two extra HTTP requests on first load (cached thereafter), and the dev rebuild caveat still applies (the `webapp` image bakes `app/` in via `COPY . ./`, so asset edits need a `docker compose up --build` to land — a live-reload bind-mount remains an optional follow-up). Verified live: page links `/static/dashboard.css|js` with `data-refresh-ms="5000"` and no inline `<style>`; assets serve 200 with correct content types; dashboard still renders 100 rows + infinite-scroll sentinel. Tests: added `test_static_assets_served` and updated `test_dashboard_has_live_feed_poller`; 27 passed, 2 skipped; ruff clean.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

### Dashboard infinite scroll (newest-first feed, server-rendered pages)
- **Decision:** The dashboard feed now orders **newest-first** (`select_edits(order="recent")`, by `classified_at`), renders the first `FEED_PAGE_SIZE` (100) rows, and loads older rows on demand via an `IntersectionObserver` that fetches server-rendered `<tr>` pages from a new `GET /fragment/rows?offset=` endpoint and appends them to the existing `<tbody>`. A hidden sentinel row carries `data-next` (the next offset; absent when exhausted). `RECENT_WINDOW_LIMIT` raised 200→500 so older pages exist to scroll into. The existing 5s live poll still refreshes the top (stats + filters + first page) and flashes newly-arrived rows.
- **Alternatives:** Client-side row rendering from `/api/edits` JSON (would duplicate the escape/link/badge logic the server already owns — an XSS-surface and drift risk); a "Load more" button (less fluid); classic pagination (worse for a live feed); keeping confidence-first ordering (kept as the API/`select_edits` default, but a time-ordered feed is the natural fit for infinite scroll).
- **Rationale / trade-offs:** Reuses the server as the single source of row markup (no JS template, no new deps, no build step — consistent with the plain-Python rendering choice), so escaping/link-safety stay in one place. Trade-off: a live poll resets appended rows back to the first page (acceptable — the newest edits are what the live view is for); and the feed is bounded by `RECENT_WINDOW_LIMIT`, so "no cap" means "up to the recent window" rather than the full table. Verified live: `/` returns 100 rows + `data-next="100"`; `/fragment/rows?offset=100` returns the next 100 + `data-next="200"`; last page drops the sentinel. All 14 dashboard tests pass.
- **Made by:** Human+Agent
- **Date:** 2026-06-08

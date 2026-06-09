# Wikipedia Edit-Triage Agent

[![CI](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml/badge.svg)](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml)

A locally-runnable system that ingests the Wikipedia recent-changes firehose,
triages each edit with a multi-step LLM reasoning loop (Redpanda Connect +
Ollama), and serves the results on a live dashboard. Built for the Redpanda
Field Deployed Engineer build exercise.

> Status: **Phase 10** — staged pipeline. Three Redpanda Connect services
> communicate via compacted topics: **ingest** (SSE → `wiki.edits.raw`) →
> **enrich** (diff fetch → `wiki.edits.enriched`) → **classify** (Ollama
> pass-1 + escalation → `wiki.edits.classified`, Postgres UPSERT, `model.audit`).
> Browse all topics in Console at <http://localhost:8090>.

## Run

**One command, from a fresh machine** (clones the repo, then starts everything):

```bash
curl -fsSL https://raw.githubusercontent.com/takabayashi/agentic-rd/main/install.sh | bash
```

**One command, from a clone:**

```bash
./start.sh        # or: make start
```

`start.sh` is a self-healing bootstrap (WarpStream-demo style): it verifies
Docker is running, seeds `.env` from `.env.example` on first run, auto-detects a
reachable host-native Ollama on Apple Silicon and points Connect at it, brings
the stack up, waits for the dashboard to report healthy, and opens it. It is
idempotent — safe to re-run.

Prefer the raw command? It still works:

```bash
docker compose up        # or: make up   (run `make help` for all shortcuts)
```

Any of these starts Postgres (schema + seed applied automatically on first run),
the web app, the Redpanda broker + Console, Ollama, and three Connect pipelines
(`connect-ingest`, `connect-enrich`, `connect-classify`). Open
<http://localhost:8080> for the triage dashboard and <http://localhost:8090> for
Redpanda Console. The dashboard fills with **live** classified edits once the
pipeline is running (it shows the seeded rows in [`db/seed.sql`](db/seed.sql)
until then).

> **Memory / environment.** The full stack (broker + Console + Connect + DB + web
> + Ollama) needs a Docker VM with **≥ 4 GB**. Docker Desktop defaults are fine
> and are the reference environment; a tiny ~1.9 GB Colima VM will **OOM-kill**
> redpanda (which is why redpanda is memory-capped in compose). On Apple Silicon,
> run Ollama on the host (see Classification) — the containerized model can crash
> under Colima.

Health, readiness, and metrics:

```bash
curl localhost:8080/healthz   # -> 200 liveness (does NOT require the DB)
curl localhost:8080/readyz    # -> 200 when the DB is reachable, else 503
curl localhost:8080/metrics   # -> Prometheus exposition (request counts + latency)
```

`/healthz` is liveness only (so an orchestrator never restarts the app during a
cold DB start); `/readyz` is the DB-backed readiness gate. If you open the
dashboard before Postgres is ready, you get a 503 "warming up" page that
auto-retries — the app never crashes on a cold or transient DB.

## Dashboard & API

- `GET /` — HTML dashboard: a table of classified edits sorted by confidence
  descending. A header stat line shows the total, the escalated count, and how
  long ago the newest row was classified. Each row links to the **article page**
  and the Wikipedia **diff** separately, shows the `#rev_id`, and a relative
  "Classified" time so you can see rows arriving live. Label-filter chips
  (`all/vandalism/substantive/trivia/unclear`) plus an **escalated** toggle
  (combinable) narrow the table. Updates are **live**: a tiny vanilla-JS poller
  (no external library, no build step) re-fetches the server-rendered
  `#feed` fragment every few seconds, swaps it in, and flashes newly-arrived
  rows — replacing the old full-page meta-refresh. A "live" dot turns grey if a
  poll fails. Rendered in plain Python (no template engine); untrusted fields
  (title, comment, editor) are escaped with `html.escape`, and links are emitted
  only for `http(s)` URIs with `rel="noopener noreferrer"`.
- `GET /fragment/edits?label=&escalated=1` — the dynamic dashboard region
  (stats + filters + table) as an HTML fragment; this is what the poller swaps
  in. The server stays the single source of markup (the client never
  re-implements row rendering).
- `GET /api/edits?label=<label>&escalated=1&limit=&offset=` — the same data as
  JSON, newest-highest-confidence first. `label` (one of `all|vandalism|
  substantive|trivia|unclear`) and `escalated=1` filter; `limit`/`offset`
  paginate; omitting them returns the whole recent window. Each row:

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
init-entrypoint **only on first start** of an empty data volume — this is the
zero-tooling bootstrap so a fresh `docker compose up` always works. To re-apply
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

**Migrations (forward schema evolution).** Beyond the first-boot bootstrap, the
schema is owned by [Alembic](https://alembic.sqlalchemy.org/) — a single
SQLAlchemy table definition in [`app/triage/schema.py`](app/triage/schema.py) is
the source, and a one-shot `migrate` compose service runs `alembic upgrade head`
before the app and the classify sink start. The initial revision uses an
idempotent `create_all(checkfirst=True)`, so it's a safe no-op on a volume
already bootstrapped by `db/init.sql` and simply records the baseline; future
schema changes ship as new revisions under
[`app/migrations/versions/`](app/migrations/versions/). A schema-contract test
([`app/tests/test_schema_contract.py`](app/tests/test_schema_contract.py)) keeps
`EditView`, `db/init.sql`, and `triage.schema` from drifting apart.

## Pipeline (staged: topics as protocol)

Three [Redpanda Connect](https://docs.redpanda.com/redpanda-connect/) services
hand off edits via compacted topics (key = `rev_id`):

| Service | Config | Role |
|---------|--------|------|
| `connect-ingest` | [`connect/ingest.yaml`](connect/ingest.yaml) | SSE → filter/project → `wiki.edits.raw` |
| `connect-enrich` | [`connect/enrich.yaml`](connect/enrich.yaml) | diff fetch → `wiki.edits.enriched` |
| `connect-classify` | [`connect/classify.yaml`](connect/classify.yaml) | Ollama agent + sink fan-out |

```
Wikipedia SSE → ingest → wiki.edits.raw → enrich → wiki.edits.enriched
  → classify → wiki.edits.classified + Postgres + model.audit
```

Watch the pipelines:

```bash
make logs-connect   # all three services
make consume-raw    # projected edits (includes parent_rev)
make consume-enriched  # edits with diff text
```

**Ingest** ([`connect/ingest.yaml`](connect/ingest.yaml)) consumes the
[Wikipedia recent-changes SSE firehose](https://stream.wikimedia.org/v2/stream/recentchange)
with `http_client` + `stream.enabled` + the `lines` scanner. SSE frames look
like `data: {…}`; we keep only `data:` lines, strip the prefix, and
`parse_json().catch(deleted())` so heartbeats (`:ok`) and any non-JSON **fail
closed**. We drop bots, non-`edit` events, and non-article namespaces, and
scope to **English Wikipedia** (`server_name == "en.wikipedia.org"`). The
projected payload includes `parent_rev` for the enrich stage (handoff fields
live in JSON, not metadata — Kafka drops metadata between services).

**Enrich** ([`connect/enrich.yaml`](connect/enrich.yaml)) consumes
`wiki.edits.raw`, **validates the inter-stage contract** (`schema_version == 1`
and a present `rev_id`), fetches each edit's diff from the MediaWiki compare API,
and produces `wiki.edits.enriched` with `diff` in the payload. Records that fail
the contract are routed to a **dead-letter** topic (`wiki.edits.dead_letter`,
24h retention) via an output `switch` instead of being silently dropped, so
malformed handoffs are inspectable in Console rather than invisible.

Dedup is handled by compacted topic keys + the Postgres `rev_id` UPSERT; no
in-pipeline cache on this SSE source. The classify sink is covered below.

## Classification (diff-enriched, two-pass)

**Classify** ([`connect/classify.yaml`](connect/classify.yaml)) consumes
`wiki.edits.enriched` and runs the multi-step LLM agent: each edit is classified
by a **local Ollama model** through Connect `branch`es. Results are persisted to
Postgres and streamed to topics (see "Sink" below):

```bash
docker compose logs -f connect-classify   # classify + sink activity
make labels escalations                   # from classify logs
```

How it works:

- **Fetch the real diff (the actual evidence).** Handled in `connect-enrich`. The
  recentchange SSE event is only edit *metadata* — never the changed text. The
  enrich service fetches each edit's diff from the MediaWiki REST compare API,
  keeps only changed lines (`+` / `-` / `~`), truncates to ~4 KB, and puts
  `diff` in the enriched topic payload. The fetch fails **closed** (empty diff,
  classification still proceeds on metadata). Rate limit: `wiki_api`, 10/s.
- **Two passes (cost vs. accuracy).** Pass-1 classifies every survivor from the
  diff + metadata. A confidence `switch` then escalates only the ambiguous ones —
  `confidence < CONFIDENCE_THRESHOLD` (default `0.7`) **or** `label == unclear` —
  to a second, more rigorous pass that re-reads the same diff with a detailed
  per-label rubric, the editor identity (an anonymous IP is a vandalism signal),
  and the first-pass result for self-critique. Confident pass-1 rows skip the
  second model call (`escalated = false`); escalated rows are stamped
  `escalated = true`. Lower `CONFIDENCE_THRESHOLD` to escalate less; raise it to
  escalate more.
- **Retries on bad output (and an unreachable model).** We deliberately *do not*
  run an in-pipeline retry loop. A malformed/empty reply — or a record the
  `branch` couldn't classify at all because the model was unreachable (Connect
  skips `result_map` when a branch's inner call fails) — falls back to `unclear`
  via a fail-safe default, so a row is never emitted with an empty label and the
  escalation `switch` never compares a null confidence. A later, more confident
  pass corrects the row via the Postgres UPSERT (Phase 7). On a noisy firehose
  this keeps latency/cost bounded and self-corrects, which we prefer over
  blocking retries (we'd flip if classifications were authoritative).
- **Local LLM via Ollama.** A pinned `ollama` service serves the model; a
  one-shot `ollama-pull` preloads it on startup, and `connect-classify` waits for
  that to complete so there's no cold-start "model not found" race. First run
  downloads the model (`llama3.2`, ~2 GB); later runs reuse the cached `ollama`
  volume. Ingest and enrich start without waiting on Ollama.
- **Change the model.** Set `OLLAMA_MODEL` (any Ollama model name) in `.env`; it
  is pulled automatically. `OLLAMA_ADDRESS` points `connect-classify` at the server.
- **Memory vs. quality.** The model loads entirely in RAM inside the Docker VM,
  so the VM needs more memory than the model size: `llama3.2` (~2 GB) wants
  roughly **4 GB+** allocated to Docker (Docker Desktop defaults are fine; with
  Colima use `colima start --memory 4` or more). On a tightly constrained VM you
  can drop to a **low-memory fallback** — `qwen2.5:1.5b` (~1 GB) or `qwen2.5:0.5b`
  (~0.4 GB) — but these classify noticeably worse (they over-label `vandalism`),
  so prefer `llama3.2` whenever the memory is available.
- **Apple Silicon / Colima → use host Ollama.** Docker can't pass through the Mac
  GPU, so the containerized Ollama runs CPU-only, and on an arm64 Colima VM the
  `ollama/ollama` image can crash during inference (a virtualization/cgo issue,
  not a pipeline bug). The reliable, fast path on a Mac is to run Ollama natively
  on the host and point Connect at it:

```bash
brew install ollama && ollama serve   # native, GPU-accelerated
ollama pull llama3.2
OLLAMA_ADDRESS=http://host.docker.internal:11434 docker compose up
```

  Connect services already map `host.docker.internal`, so only `OLLAMA_ADDRESS`
  needs to change. The containerized Ollama remains the default
  so `docker compose up` is self-contained on platforms that support it (Docker
  Desktop, Linux).
- **`branch` keeps the record intact.** `request_map` sends only the fields that
  inform a label (title, comment, `size_delta`, and the diff); `ollama_chat`
  returns JSON (`response_format: json`, `temperature: 0`); `result_map` grafts
  `{label, confidence}` back onto the original record rather than overwriting it.
  Both passes use this same pattern.
- **Robust, crash-safe parse.** We extract the first `{...}` block from the model
  reply (handles any prose around it), fall back to `{}` on failure, normalize
  the label (`trim().lowercase()`) to the enum — anything unknown or empty
  becomes `unclear` — and coerce `confidence` to a number clamped to `[0,1]`. A
  malformed or empty reply yields a valid `unclear` row instead of crashing. The
  identical parse is applied in both passes.
- **Security.** Output is constrained to the fixed enum
  (`vandalism|substantive|trivia|unclear`) in both passes, so prompt-injection in
  the attacker-controlled title/comment/diff can't change system behavior; the
  classification is advisory only. No edit data is sent to any third-party model
  (inference is local); the only outbound calls are the public Wikipedia SSE feed
  and the read-only diff fetch (which sends just revision ids).

## Sink: topics, Console & UPSERT

`connect-classify` ends with a `broker` fan-out (in
[`connect/classify.yaml`](connect/classify.yaml)) to three destinations:

- **`wiki.edits.classified`** — Redpanda topic, keyed by `rev_id`, `zstd`,
  batched: the stream of classified edits. The topic is **compacted**, so it
  keeps the last value per `rev_id` (matching the UPSERT's last-write-wins).
- **Postgres `classified_edits`** via `sql_raw` **UPSERT**
  (`INSERT ... ON CONFLICT (rev_id) DO UPDATE`) — the dashboard's source. A row
  first written `unclear` on a cold-start/transient failure is corrected in
  place by a later, more confident pass; re-processing a `rev_id` updates the
  row instead of duplicating it. The SQL output is wrapped in `retry`, so a
  transient Postgres outage is retried, not fatal.
- **`model.audit`** — Redpanda topic, append-only, ~6h retention, `zstd`: one
  record per edit with both passes' raw model I/O
  (`{rev_id, model, ts, pass1{input, raw_response, label, confidence}, pass2|null}`)
  for replay / prompt-eval / drift inspection. Captured from branch metadata; it
  is *not* persisted to Postgres (a `model_calls` table sync is left for later).
  **Data/retention note:** these records embed the full prompts — including the
  attacker-controlled title/comment/diff — so they're untrusted content. The
  short time-retention (not compaction) bounds how long that text lives; for a
  real deployment, lengthen retention deliberately, restrict topic ACLs, and
  treat audit data as sensitive (scrub/encrypt as policy requires).

Browse the topics in **Console** at <http://localhost:8090>, or from the CLI:

```bash
make consume-raw N=3
make consume-enriched N=3
make consume-classified N=5
make consume-audit N=2
```

- **Routing.** The brief's "route" requirement is met by the confidence `switch`
  (routing ambiguous edits to the escalation pass) plus a single labeled topic
  (the `label` field) — a deliberate choice over topic-per-label.
- **Compression.** Producer-side `zstd` on the topic outputs (text JSON +
  wikitext diffs compress well), paired with batching for a better ratio;
  transparent to Console/consumers.

Ports: dashboard `8080`, Console `8090`, classify Connect metrics `4195`.

## Observability

Lightweight, local, no external stack required:

- **App metrics** — `GET /metrics` on the dashboard exposes Prometheus request
  counts + latency (labelled by method, route template, status). Instrumented by
  a small ASGI middleware ([`app/triage/metrics.py`](app/triage/metrics.py)).
- **Pipeline metrics** — each Connect service serves Prometheus metrics on
  `:4195` (`metrics: { prometheus: {} }`); the classify stage's port is mapped to
  the host (`http://localhost:4195/metrics`) for input/output/processor counters,
  latencies, and errors.
- **Structured logs** — the app logs one-line JSON per record
  ([`app/triage/logging_config.py`](app/triage/logging_config.py)) for easy
  grep/aggregation; Connect logs `logfmt`.
- **Readiness** — `GET /readyz` (DB-backed) vs `GET /healthz` (liveness).

Point any Prometheus at `localhost:8080/metrics` and `localhost:4195/metrics` to
scrape the app and the classify pipeline.

## Develop / test

A root [`Makefile`](Makefile) wraps the common workflow — run `make help` for the
full list. Highlights:

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

### Testing

The core suite is **DB-free**: it mocks `get_recent_edits` with an in-memory
fixture, so `make test` runs without Postgres or the broker. One optional
integration test ([`tests/test_integration_db.py`](app/tests/test_integration_db.py))
spins up a throwaway Postgres via testcontainers and **skips automatically when
Docker isn't available**, so it never blocks the DB-free path.

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
| Schema contract | `tests/test_schema_contract.py` | `EditView` ↔ `db/init.sql` ↔ `triage.schema` agree |
| Integration | `tests/test_integration_db.py` | real Postgres via testcontainers (skips if Docker absent) |

Connect Bloblang now has a real unit-test harness too: `make connect-test` runs
the parse/normalize/clamp cases ([`connect/tests/`](connect/tests/)) against the
actual shared library ([`connect/lib/classification.blobl`](connect/lib/classification.blobl)),
and `make connect-lint` validates every pipeline config. Live e2e remains the
final check.

Layout:

```text
start.sh             # one-command bootstrap (preflight, .env, wait-for-health)
install.sh           # curl | bash fresh-machine installer (clones + start.sh)
app/
  triage/            # the application package
    main.py          # composition root: app + router + metrics + JSON logging
    config.py        # typed settings (pydantic-settings)  (config)
    models.py        # EditView + Label enum + select_edits()  (domain)
    schema.py        # SQLAlchemy table = Alembic schema source  (data)
    repository.py    # Postgres access: get_recent_edits, check_ready  (data)
    web.py           # HTTP layer: dashboard, /fragment/edits, /api/edits, /healthz, /readyz, /metrics
    render.py        # plain-Python HTML rendering + live-feed poller
    styles.py        # extracted CSS constants
    metrics.py       # Prometheus middleware + /metrics payload
    logging_config.py # one-line JSON logging
  migrations/        # Alembic env + versions/ (forward schema evolution)
  tests/             # pytest suite + sample_data fixture
  Dockerfile
  requirements.txt
db/                  # init.sql (first-boot schema) + seed.sql
connect/             # ingest/enrich/classify pipelines + lib/ (shared Bloblang) + tests/
Makefile             # dev/test shortcuts (make help)
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed (`./start.sh` does this for
you on first run, and also generates a random `POSTGRES_PASSWORD` so local runs
don't use the well-known `change-me`). `.env` is gitignored — no secrets are
committed. `.env` is optional: `docker-compose.yml` supplies safe local defaults,
so a fresh clone still runs with just `docker compose up`.

| Variable | Default | Used by | Purpose |
|----------|---------|---------|---------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `wiki` / `change-me` / `wiki` | postgres, app, migrate, classify | DB credentials (compose builds `DATABASE_URL`/`POSTGRES_DSN`) |
| `RECENT_WINDOW_LIMIT` | `200` | app | recent rows fetched before in-app filter/sort |
| `WIKI_USER_AGENT` | repo default | ingest, enrich | Wikipedia requires a descriptive UA (403 otherwise) |
| `DIFF_MAX_CHARS` | `4000` | enrich | truncate fetched diffs to this many chars |
| `WIKI_RATE_LIMIT` | `10` | enrich | MediaWiki compare-API calls/sec (politeness) |
| `OLLAMA_MODEL` / `OLLAMA_ADDRESS` | `llama3.2` / `http://ollama:11434` | classify, pull | model + server (set host address on Apple Silicon) |
| `CONFIDENCE_THRESHOLD` | `0.7` | classify | escalate edits below this confidence |

**Secrets.** Credentials come only from env/`.env` (never tracked); SQL is
parameterized and DSNs carry no creds in logs. For a real deployment, move the
DB password to Docker/Compose secrets or an external manager (Vault, cloud
secrets) and scope topic ACLs — the local default flow is convenience, not a
production secret posture.

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
of scope (see [`docs/TODO.md`](docs/TODO.md) "Out of scope").

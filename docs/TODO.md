# Implementation TODO — Wikipedia Edit-Triage Agent

Incremental build plan derived from [`docs/requirements.md`](./requirements.md) and
the take-home brief ([`docs/RedpandaTakehome.pdf`](./RedpandaTakehome.pdf)). Each
phase is small, independently verifiable, and ends in a runnable state.

**Conventions**
- `[ ]` = not started, `[x]` = done.
- Every phase carries lightweight **Security** and **Docs** notes plus an explicit
  **Acceptance criteria** block (each criterion is testable / observable).
- Do one phase at a time; don't start the next until acceptance criteria pass.

**Scope discipline (why this list is short).** The brief is an explicit
*couple-of-hours* exercise graded on judgment, not surface area: "plain but
works", "one command brings it up", "README is short and honest". So the plan
builds exactly the evaluated path — **ingest → transform → reason → serve** — and
deliberately omits gold-plating (deploy automation, dependency bots, a metrics
stack, elaborate UI). Anything cut is listed under **Out of scope** with a reason.

> **Revision (this pass):** consolidated 13 phases → 10. Merged Connect ingest +
> transform, merged Ollama infra + pass-1, folded the standalone "observability"
> phase's *useful* parts (output retries/backoff + clean logs) into the end-to-end
> sink phase and dropped the metrics view, trimmed UI and test scope to
> "plain but works", and capped CI at the lightweight setup already in place
> (no further CI/CD expansion). The required README write-up keeps its own final
> phase because it is the most heavily graded deliverable.

---

## Phase 0 — Project skeleton & health *(done)*

> Goal: a repo that starts cleanly with one command and serves a trivial page.

- [x] `git init`; `.gitignore` (`.env`, `__pycache__`, `.venv`, `.DS_Store`)
- [x] `app/main.py`: FastAPI with `GET /` → `{"status":"ok"}` and `GET /healthz` → 200
- [x] `app/requirements.txt` (fastapi, uvicorn) + `app/Dockerfile` (pinned base image)
- [x] `app/tests/test_health.py`: asserts `/healthz` returns 200
- [x] `docker-compose.yml` with the `webapp` service on port 8080
- [x] **Security:** `.env.example`; `.env` gitignored; pinned image tags; no secrets committed
- [x] **Docs:** `README.md` skeleton — one-line description + "Run" section

**Acceptance criteria**
- [x] `docker compose up` starts cleanly and the webapp stays running
- [x] `curl localhost:8080/healthz` → HTTP 200
- [x] `pytest` passes locally
- [x] `git status` shows `.env` ignored; no secret values tracked

## Phase 1 — Lightweight CI *(done; intentionally minimal)*

> Goal: every push is linted, built, and tested so the repo stays trustworthy.
> Deliberately capped here — CI is **not** part of the brief, so it stays small.

- [x] GitHub Actions: `ruff` lint + format check, `pytest`, `docker compose build`
- [x] Secret-scan job (`gitleaks`) over full history; least-privilege `GITHUB_TOKEN` (`contents: read`)
- [x] **Security:** `gitleaks` clean; no secrets in tracked files
- [x] **Docs:** README "CI/CD" section + status badge

**Acceptance criteria**
- [x] `ruff check` / `ruff format --check` / `pytest` / `gitleaks detect` pass locally
- [ ] First push to GitHub shows the workflow green *(verify once, non-blocking)*

> **Capped scope:** GHCR deploy, Dependabot, branch-protection, and extra
> Dockerfile/YAML linters are extras beyond the brief. The minimal pieces that
> already exist are kept; **no further CI/CD work is planned** (see Out of scope).

## Phase 2 — Dashboard with mocked data

> Goal: the moderator view exists and looks right, fed by a hardcoded fixture.
> No DB or pipeline yet — nail the "plain but works" view first.

- [x] Define the edit view-model (`rev_id, title, editor, comment, label, confidence, escalated, size_delta, uri, event_ts, classified_at`) — `app/models.py`
- [x] `MOCK_EDITS` fixture covering all 4 labels + one escalated row + empty state (`AGENTIC_EMPTY=1`) — `app/mock_data.py`
- [x] Jinja2 table: label badge, confidence, title link (`rel="noopener noreferrer"`), Δbytes, comment, time; sorted by confidence desc; label filter links (`all/vandalism/substantive/trivia/unclear`) with counts; 15s auto-refresh
- [x] `GET /api/edits?label=` returning the view-model as JSON
- [x] **Security:** confirmed Jinja2 autoescaping is ON (title/comment are untrusted attacker text); external links `rel="noopener noreferrer"`
- [x] **Docs:** documented the `/api/edits` response shape (README "Dashboard & API")

**Acceptance criteria**
- [x] `/` renders all 4 label badges + an escalated marker, sorted by confidence desc
- [x] A label filter narrows the table
- [x] `/api/edits?label=vandalism` returns only vandalism rows as valid JSON
- [x] A `<script>` injected in a mock title renders escaped (not executed)

## Phase 3 — Postgres: schema, seeds, real serving

> Goal: the UI reads from a real store instead of mocks.

- [x] Add `postgres:16` (pinned `16.14`) to compose with a `pg_isready` healthcheck; gate `webapp` on `service_healthy`
- [x] `db/init.sql`: `classified_edits` (`rev_id` BIGINT PK, `label` CHECK enum, confidence 0–1 CHECK, escalated, timestamps, `event_ts DESC` index)
- [x] `db/seed.sql` (mirrors the Phase 2 fixture, idempotent `ON CONFLICT`) so the dashboard has data without the pipeline
- [x] Swap the mock source → parameterized `psycopg` query in `app/db.py` (`get_recent_edits`); DB-not-ready fallback (graceful 503 warm-up, no crash)
- [x] **Security:** DB creds from env only (`POSTGRES_*` / `DATABASE_URL`); SQL is parameterized (`%s`, no interpolation); default-password change documented
- [x] **Docs:** schema doc (columns + why `rev_id` PK / UPSERT rationale); `psql` connect snippet (README "Database")

**Acceptance criteria**
- [x] `docker compose up` brings up Postgres healthy and the app serves seeded rows
- [x] `/` and `/api/edits` reflect `db/seed.sql` (5 rows; `?label=vandalism` → 1)
- [x] Stopping Postgres yields a graceful 503 (no crash); restarting recovers (verified: 200)
- [x] An out-of-enum label is rejected by the CHECK constraint (`classified_edits_label_check`)

## Phase 4 — Connect ingest + transform (filter, project)

> Goal: pull the real firehose and turn it into a clean, model-ready schema.
> No LLM yet — temporary `stdout` sink. **Connect-only**: the broker + Console
> are deferred to the sink phase (nothing consumes a topic yet), and dedup is
> deferred to the Postgres `rev_id` UPSERT (Phase 7), so no in-pipeline cache.

- [x] Standalone `connect` service (pinned `connect:4.95.0`) mounting `connect/wikipedia.yaml`: `http_client` SSE input (`stream.enabled`, `lines` scanner, `omit_empty`) with descriptive `User-Agent`
- [x] Parse frames: keep `data:` lines, strip prefix; `parse_json().catch(deleted())` to fail-closed on heartbeats (not `if`)
- [x] Filter + project in one pass (root rebuilt as a whole object): keep `type=edit`, `bot=false`, `namespace=0`, **`server_name=en.wikipedia.org`**; build clean schema incl. `size_delta` (int64); `deleted()` the rest
- [x] Convert epoch → ISO for `event_ts` (TIMESTAMPTZ-safe) via `ts_format`, fallback to `meta.dt`; cast `rev_id`/`size_delta` to int64 (avoids float/sci-notation in the diff URL)
- [x] **Security:** set `WIKI_USER_AGENT` (Wikipedia 403s without it); treat title/comment as untrusted data throughout
- [x] **Docs:** document source choice, SSE quirks, the User-Agent requirement, the filter rationale (incl. en.wikipedia scoping)

**Acceptance criteria**
- [x] Connect logs a steady stream of clean projected JSON to stdout
- [x] Only main-namespace, non-bot English-Wikipedia `edit`s survive; each has all schema fields
- [x] `event_ts` is valid ISO-8601 (no raw epoch); `size_delta` correct (incl. negatives)
- [x] Runs ≥2 min without crashing on heartbeats / non-JSON lines (validated: 0 restarts, 0 errors, 239 records)

> Dedup criterion moved to Phase 7 (Postgres `rev_id` UPSERT is the durable
> backstop; SSE rarely re-sends a `rev_id`).

## Phase 5 — LLM pass-1 classification (Ollama) + robust parse

> Goal: a reachable local model gives every surviving edit a normalized
> `{label, confidence}`.

- [x] `ollama` service + one-shot `ollama-pull` to preload the model; gate `connect` on pull completion (`OLLAMA_MODEL`, `OLLAMA_ADDRESS` env-configurable)
- [x] Pass-1 `branch`: `request_map` builds the prompt (title + comment + `size_delta`); `ollama_chat`; `result_map` grafts result back (don't overwrite the record)
- [x] Robust parse: extract first `{...}` block, fallback `{}` on failure, normalize label to the enum (`.string().trim().lowercase()` + map), default `unclear`, coerce confidence to a number
- [x] **Security:** constrain output to the fixed enum so prompt-injection can't change behavior; result is advisory only (no data leaves the host)
- [x] **Docs:** document model choice + how to change it; first-run pull time; the pass-1 prompt + parse/normalize rules

**Acceptance criteria**
- [x] `ollama-pull` completes; model appears in `ollama list`; `connect` waits (no cold-start "model not found" race)
- [x] Records carry `label ∈ {vandalism,substantive,trivia,unclear}` and `confidence ∈ [0,1]` (validated live: e.g. "We use miles in the UK not KM" → vandalism, infobox fixes → substantive)
- [x] Dirty JSON (prose around `{...}`) still parses to a valid label (validated: prose-wrapped `{...}` → `vandalism`)
- [x] Out-of-enum label normalizes to `unclear`; malformed/empty reply defaults to `unclear` without crashing (validated: `spam`→`unclear`, non-JSON→`unclear`/0, confidence 5→1, -2→0)

> **Validation note (env-specific):** the in-container `ollama/ollama` image
> crashes during inference on this host's arm64 Colima VM (native/cgo `fatal
> error: found bad pointer in Go heap`; older `0.24.0` OOM-crashes too) — a
> Colima VZ incompatibility, not a pipeline bug. Validated end-to-end against a
> **host-native Ollama** via `OLLAMA_ADDRESS=http://host.docker.internal:11434`
> (~4.5s/inference). The containerized default is kept for portability (Docker
> Desktop / Linux runners), with the host override documented in the README.

## Phase 6 — Confidence-based escalation (the multi-step loop)

> Goal: a structured second pass for ambiguous items — the "more than one prompt"
> agent topology.

> **Scope expansion (this pass):** added a per-edit **diff fetch** (MediaWiki
> compare API) so classification reasons over the real changed text — the SSE
> event is only metadata. This supersedes the original "escalation pulls more
> diff context" framing: the diff now enriches *every* edit, and escalation is a
> re-prompt over the same diff (richer rubric + first-pass result). See
> `docs/decisions.md` (Phase 6).

- [x] Diff enrichment `branch` (MediaWiki REST compare API) → compact `+/-` diff in metadata; fail-closed to empty; `wiki_api` `local` rate limit; `log` of `rev_id` + diff length
- [x] `switch` on `confidence < CONFIDENCE_THRESHOLD || label == "unclear"` → richer escalation `branch` (rubric + editor + first-pass result); reuse the robust parse; set `escalated = true`
- [x] `CONFIDENCE_THRESHOLD` env-configurable (`${CONFIDENCE_THRESHOLD:0.7}` in the pipeline; wired into the `connect` service in compose)
- [x] Decide retries-on-bad-output explicitly: **fallback-to-`unclear` + later UPSERT correction** instead of an in-pipeline retry loop; document the why (latency/cost vs. self-correcting convergence)
- [x] **Security:** same enum-constraint + advisory-only guarantees apply to pass 2
- [x] **Docs:** document why two passes (cost vs. accuracy) and when escalation triggers

**Acceptance criteria**
- [x] High-confidence pass-1 records skip the 2nd call (`escalated = false`)
- [x] Low-confidence / `unclear` records trigger pass 2 (`escalated = true`)
- [x] Lowering `CONFIDENCE_THRESHOLD` measurably reduces escalations
- [x] Pass-2 output is enum-normalized and crash-safe

## Phase 7 — Dual sink end-to-end + connector hardening

> Goal: persist durably and stream; make the connector production-shaped
> (retries, batching, useful logs). Removes the temporary stdout.

- [x] `broker` fan-out: Redpanda topic `wiki.edits.classified` (key = `rev_id`, compacted) via the native `redpanda` output; broker + Console (`:8090`) + `redpanda-topics` one-shot added to compose
- [x] Routing note: ONE labeled topic (`label` field) + the confidence `switch` is the routing logic (not topic-per-label) — stated so the brief's "route" requirement is traceable
- [x] `sql_raw` to `classified_edits` with `ON CONFLICT (rev_id) DO UPDATE` (UPSERT, `sql_insert` can't); stamp `classified_at`; wrapped in `retry`; removed the temporary `stdout`
- [x] Connector hardening: `retry` on the SQL sink + batching + `compression: zstd` on the topic outputs (per-batch, so it pairs with batching — bigger batches → better ratio; transparent to consumers/Console); healthcheck-gated `depends_on`
- [x] **(Extension) Model audit topic** `model.audit` (append-only, ~6h retention — *not* compacted; key = `rev_id`): a second fan-out output capturing one record per edit with both passes' raw model I/O — `{rev_id, model, ts, pass1{input, raw_response, label, confidence}, pass2{…}|null}`. Raw responses stashed in metadata during each `branch`, reshaped in the audit output's `processors`. For replay / prompt-eval / drift inspection; sync to a `model_calls` table later if needed.
- [x] **Security:** DSN from env (built from `POSTGRES_*`); explicit `sslmode=disable` (local); no creds in logs
- [x] **Docs:** document the topic(s), browsing them in Console, and how UPSERT corrects cold-start `unclear` rows

**Acceptance criteria**
- [x] Fresh `docker compose up` fills the dashboard with live classified edits
- [x] Messages appear on `wiki.edits.classified` (keyed by `rev_id`) in Console
- [x] Re-processing a `rev_id` updates the existing row (no PK collision/duplicate)
- [x] A first-pass `unclear` row is later corrected by an UPSERT (no permanently stuck rows)
- [x] Logs clearly show ingest → classify → sink without flooding; transient Postgres/Ollama downtime is retried, not fatal
- [x] (Extension) Each classified edit emits an audit record on `model.audit` carrying both passes' raw input/output; topic uses time-retention (no compaction)
- [x] Topic outputs use `zstd` compression (observable via reduced on-disk size / batch compression in Console or Redpanda metrics)

> **Also shipped this pass (extras, beyond the original Phase 7 list):** a dev
> `Makefile` (`make help`); redpanda memory cap + a Docker-Desktop reference-env
> note (a ~1.9 GB Colima VM OOM-kills the broker); and dashboard UX for easier
> testing — header freshness stats, a "Classified N ago" column, an escalated
> filter (also `/api/edits?escalated=1`), and per-row article + diff links + rev
> id. All logged in `docs/decisions.md`.

## Phase 10 — Staged Connect pipeline (topics as protocol)

> Goal: split the monolithic Connect job into three services that communicate via
> compacted Kafka topics; classify remains the Connect-based agent (Ollama).

- [x] `connect/ingest.yaml`: SSE → filter/project → `wiki.edits.raw` (`parent_rev` in payload)
- [x] `connect/enrich.yaml`: consume raw → diff fetch → `wiki.edits.enriched` (`diff` in payload)
- [x] `connect/classify.yaml`: consume enriched → pass-1 + escalation → fan-out sink (strip handoff fields before Postgres)
- [x] `docker-compose.yml`: `connect-ingest`, `connect-enrich`, `connect-classify`; create `wiki.edits.raw` + `wiki.edits.enriched` topics
- [x] `Makefile`: lint/logs/restart/consume targets for all three services
- [x] **Docs:** decision entry, README architecture, requirements Flow 2, `.env.example` service scoping

**Acceptance criteria**
- [x] `docker compose up` brings up all three Connect services; `make topics` lists four topics
- [x] `make consume-raw` / `consume-enriched` / `consume-classified` show records at each stage
- [x] Dashboard fills with live classified edits; UPSERT still dedupes by `rev_id`
- [x] `make check` passes (lint all three YAMLs + pytest)

## Phase 8 — Focused automated tests

> Goal: lock in the gnarly bits (parsing/edge cases) without a heavy harness.

- [x] App unit tests: label filter, parameterized query, JSON serialization, empty + 503 states, and HTML-escapes-a-malicious-`<script>` title
- [x] Connect parse/normalize: `connect-lint` + e2e (no Python mirror — avoids drift with Bloblang)
- [x] Wire tests into the CI `test` job (+ `connect-lint` job for pipeline YAMLs)
- [x] **Security:** the escaping test doubles as an XSS regression guard
- [x] **Docs:** README "Testing" section — how to run + what's covered

**Acceptance criteria**
- [x] `pytest` passes locally and in CI; each edge case above has ≥1 assertion
- [ ] CI fails if any test fails (verify with a temporary deliberate break, then revert)

> Full Redpanda Connect test-harness coverage of every Bloblang mapping is
> **optional** (listed in Out of scope) — `connect-lint` + e2e cover pipeline
> logic; pytest covers the web app only.

## Phase 9 — Required write-up & repro polish *(deliverable)*

> Goal: the graded README write-up and a clean one-command repro. This is the
> most heavily evaluated artifact — give it real time.

- [ ] README **Tradeoffs** section (½–1 page) — name the alternative + when you'd flip + what shaped the thinking, for two pairs:
  - [ ] Pair A: **one classification call vs. a multi-step reasoning loop** (we built the loop: pass-1 + confidence escalation)
  - [ ] Pair B: **Connect as the sink vs. app-side writes from a topic** (we chose Connect `sql_insert` UPSERT)
- [ ] README **Surprises** paragraph + **"where this breaks in production"** paragraph
- [ ] README final polish: copy-pasteable run, architecture diagram, ports table, configurable env vars
- [ ] **Security:** final pass — `gitleaks` clean on full history; localhost-only noted; deps pinned
- [ ] **Docs:** `.env.example` complete; every documented step reproducible from a fresh clone

**Acceptance criteria**
- [ ] A teammate following only the README reaches visible classified edits from a fresh clone
- [ ] Tradeoffs section names alternatives + flip conditions (not boilerplate)
- [ ] Surprises + production-failure paragraphs are present and specific
- [ ] `docker compose up` is the only required command (no forgotten manual steps)

## Phase 11 — One-command start + arch/maintainability hardening

> Goal: a WarpStream-style one-command start, plus the full set of arch and
> maintainability improvements from the codebase review. Intentionally exceeds
> the original "plain but works" cap (requested explicitly). Connect-side items
> were authored without local Docker — they require `make connect-lint` +
> `make connect-test` + an e2e `docker compose up` to validate.

- [x] One-command start: `start.sh` (preflight, `.env` seed, random DB password, Apple-Silicon host-Ollama, wait-for-health, open) + `install.sh` (`curl | bash`) + `make start`
- [x] Align Python to `3.12.13` across `app/Dockerfile`, CI, `ruff.toml`
- [x] DRY the classify parse/enum into `connect/lib/classification.blobl` (imported by both passes)
- [x] Typed config (`triage/config.py`, pydantic-settings); lazy single-pool repository; `check_ready()`
- [x] Observability: `/metrics` (Prometheus) + JSON logging; Connect `prometheus` metrics on all stages (classify `:4195`); `/readyz`
- [x] Live-feed poller (`/fragment/edits`) replacing meta-refresh; `/api/edits` pagination; CSS extracted to `styles.py`
- [x] ~~Alembic migrations~~ dropped — `db/init.sql` only; static local DB password
- [x] Inter-stage `schema_version` contract + `wiki.edits.dead_letter` topic (enrich)
- [x] Named tunables: `RECENT_WINDOW_LIMIT`, `DIFF_MAX_CHARS`, `WIKI_RATE_LIMIT`
- [x] Tests: schema-contract, `/readyz` + `/metrics`, testcontainers Postgres integration, Connect Bloblang harness (`make connect-test`); both wired into CI
- [x] Static local DB password (`change-me` in compose); secrets/`model.audit` retention notes (README)
- [x] Docs: README (one-command, observability, migrations, dead-letter, config table), `decisions.md`, this file

**Acceptance criteria**
- [x] `ruff check` / `ruff format --check` / `yamllint` / `pytest` pass locally (26 passed, 2 integration skipped without Docker)
- [ ] `make connect-lint` + `make connect-test` pass *(needs Docker — not run in the authoring env)*
- [ ] `./start.sh` brings the full stack up to a healthy dashboard from a fresh clone *(needs Docker)*
- [ ] `docker compose up` brings the stack up, dashboard fills with live classified edits, dead-letter stays empty for well-formed records *(needs Docker)*

---

## Out of scope (deliberately cut — see PRD)

These are tracked, not built, to honor the "couple-of-hours / plain but works" brief:

- **CI/CD expansion:** GHCR deploy automation, Dependabot, branch protection,
  hadolint/yamllint jobs — the brief doesn't ask for CI; what exists is kept minimal.
- **Observability stack:** metrics/counter view, dashboards, alerting (container
  logs are enough); only output retries/backoff + clean logs are in (Phase 7).
- **Full Connect test harness** for every Bloblang mapping (app-level parse tests
  cover the risky logic instead).
- Cloud/production deployment, multi-node Redpanda, managed Postgres, secrets manager.
- AuthN/AuthZ + multi-user accounts on the dashboard.
- Hosted LLM as default (local Ollama is primary; hosted left as an optional
  `.env.example` path); automated moderation actions; historical backfill.
- Multi-source ingestion (HN / USGS / GitHub) — single source by design.

# Implementation TODO — Wikipedia Edit-Triage Agent

Incremental build plan derived from [`docs/requirements.md`](./requirements.md).
Each phase is small, independently verifiable, and ends in a runnable state —
suited to AI-assisted development.

**Conventions**
- `[ ]` = not started, `[x]` = done.
- Every phase carries **Security** and **Docs** tasks plus an explicit
  **Acceptance criteria** block (each criterion is testable / observable).
- Do one phase at a time; don't start the next until acceptance criteria pass.

> **Revision notes (this pass):** split the old "LLM loop" phase into infra →
> pass-1 → pass-2; split observability from the required write-up; added a real
> health test in Phase 0 so the CI test job has something to run; merged
> inseparable Connect steps; and gave every phase explicit acceptance criteria.

---

## Phase 0 — Project initialization & "Hello World"

> Goal: a repo that starts cleanly with one command and serves a trivial page.
> Deployable from here on.

- [x] `git init`; add `.gitignore` (`.env`, `__pycache__`, `.venv`, `.DS_Store`)
- [x] Create `app/main.py`: FastAPI with `GET /` → `{"status":"ok"}` and `GET /healthz` → 200
- [x] Add `app/requirements.txt` (fastapi, uvicorn) + `app/Dockerfile` (pinned base image)
- [x] Add `app/tests/test_health.py`: asserts `/healthz` returns 200 (gives CI a real test in Phase 1)
- [x] Write `docker-compose.yml` with just the `webapp` service on port 8080
- [x] **Security:** add `.env.example`; confirm `.env` is gitignored; pin all image/base tags; no secrets committed
- [x] **Docs:** `README.md` skeleton — one-line description + "Run" section (`docker compose up`, open `http://localhost:8080`)

**Acceptance criteria**
- [x] `docker compose up` starts with no errors and the webapp stays running
- [x] `curl localhost:8080/healthz` → HTTP 200
- [x] `pytest` passes locally (1 test)
- [x] `git status` shows `.env` ignored; no secret values in tracked files

## Phase 1 — CI/CD pipeline (set up early)

> Goal: every push is linted, built, and tested automatically; a deploy path exists.

- [x] GitHub Actions workflow: checkout + `ruff` lint + format check
- [x] CI job: `docker compose build` (proves images build)
- [x] CI job: `pytest` (runs the Phase 0 health test)
- [x] Add `hadolint` (Dockerfile) + `yamllint` (compose/Connect YAML)
- [x] Deploy stub: build & push image to GHCR on tag *or* a documented manual deploy
- [x] **Security:** enable Dependabot; add `gitleaks` secret-scan job; set least-privilege `permissions:` on `GITHUB_TOKEN`
- [x] **Docs:** README "CI/CD" section + status badge; note branch-protection expectations

**Acceptance criteria**
- [ ] Opening a PR runs all jobs and they pass (green) — verify on GitHub after first push
- [ ] Lint catches a deliberately introduced style error (spot-check), then is reverted
- [x] `gitleaks` job runs and reports clean — validated locally (`gitleaks detect`, no leaks)
- [ ] Tagged commit produces a published image *or* deploy docs are followed successfully — verify after pushing a `v*` tag

## Phase 2 — Basic UI with mocked data

> Goal: the moderator dashboard exists and looks right, fed by hardcoded rows.
> No DB, no pipeline yet.

- [ ] Define the edit view-model (rev_id, title, editor, comment, label, confidence, escalated, size_delta, uri, event_ts, classified_at)
- [ ] Add `MOCK_EDITS` fixture: all 4 labels + one escalated row (+ ability to render the empty state)
- [ ] Build the Jinja2 table view: confidence, label badge, title link, Δbytes, comment, time
- [ ] Add label filter links (`all/vandalism/substantive/trivia/unclear`), sort by confidence desc, label counts header, auto-refresh, empty-state message
- [ ] Add `GET /api/edits?label=` returning the mock data as JSON
- [ ] **Security:** confirm Jinja2 autoescaping is ON (title/comment are untrusted); add `rel="noopener"` to external links
- [ ] **Docs:** add a dashboard screenshot to README; document `/api/edits` response shape

**Acceptance criteria**
- [ ] Dashboard at `/` renders all 4 label badges and an escalated marker
- [ ] Clicking a label filter narrows the table; rows are sorted by confidence desc
- [ ] `/api/edits?label=vandalism` returns only vandalism rows as valid JSON
- [ ] A `<script>` injected in a mock title renders escaped (not executed)

## Phase 3 — Postgres + serving real (seeded) data

> Goal: the UI reads from a real store instead of mocks.

- [ ] Add `postgres:16` service to compose with a healthcheck; gate `webapp` on it
- [ ] Write `db/init.sql`: `classified_edits` (rev_id PK, label CHECK enum, confidence, escalated, timestamps, indexes)
- [ ] Add `db/seed.sql` so the dashboard has data without the pipeline
- [ ] Swap the app from `MOCK_EDITS` to parameterized `psycopg` queries; add a connection-not-ready fallback (503 + warm-up message)
- [ ] **Security:** DB creds from env only; document changing the default password; parameterize all SQL (no string interpolation of inputs)
- [ ] **Docs:** schema doc (columns + why `rev_id` is PK / UPSERT rationale); how to connect with `psql`

**Acceptance criteria**
- [ ] `docker compose up` brings up Postgres healthy and the app serves seeded rows
- [ ] `/` and `/api/edits` reflect `db/seed.sql` contents
- [ ] Stopping Postgres makes `/` return a graceful 503 warm-up page (no crash); restarting recovers
- [ ] Inserting a row with an out-of-enum label is rejected by the CHECK constraint

## Phase 4 — Redpanda broker + Connect ingest skeleton

> Goal: pull the real firehose and log parsed records. No transform/LLM yet.

- [ ] Add `redpanda` (`--mode=dev-container`) + `console` services with healthchecks
- [ ] Add `connect` service mounting `connect/wikipedia.yaml` with `http_client` SSE input (`stream.enabled`, `lines` scanner) + `User-Agent` header
- [ ] Parse SSE frames: strip `data:` prefix; `parse_json().catch(deleted())` to fail-closed on heartbeats; temporary `stdout` output
- [ ] **Security:** set descriptive `WIKI_USER_AGENT` (Wikipedia 403s without it); confirm no tokens needed for this source
- [ ] **Docs:** document the source choice, SSE quirks, and the User-Agent requirement

**Acceptance criteria**
- [ ] Connect logs show a steady stream of parsed JSON edit objects to stdout
- [ ] Removing the User-Agent reproduces a 403 (confirming why it's required), then restored
- [ ] Pipeline runs ≥2 min without crashing on heartbeat / non-JSON lines
- [ ] Redpanda Console is reachable and the cluster is healthy

## Phase 5 — Transform: filter, project, dedupe

> Goal: turn the raw firehose into a clean, deduped, model-ready schema.

- [ ] Filter before the model and project in one pass: keep `type=edit`, `bot=false`, `namespace=0`; build the clean schema incl. `size_delta`; `deleted()` the rest
- [ ] Convert epoch → ISO for `event_ts` (TIMESTAMPTZ-safe), fallback to `meta.dt`
- [ ] Add in-memory `cache` dedupe keyed on `rev_id`; drop on cache-add error
- [ ] **Security:** treat title/comment as untrusted text throughout (carried as data, never executed/interpolated)
- [ ] **Docs:** document filter rationale (cost/noise) and the dedupe strategy

**Acceptance criteria**
- [ ] Only main-namespace, non-bot edits appear downstream (bots/other namespaces dropped)
- [ ] Each projected record has all schema fields; `size_delta = size_new - size_old`
- [ ] `event_ts` is a valid ISO-8601 string (no raw epoch)
- [ ] Emitting the same `rev_id` twice yields one downstream record
- [ ] A trailing mapping doesn't wipe other fields (root rebuilt from `this`)

## Phase 6 — LLM infrastructure (Ollama) + single-call smoke test

> Goal: a reachable local model and proof a single classification call works.

- [ ] Add `ollama` service + `ollama-pull` one-shot to preload the model; gate `connect` on pull completion
- [ ] Add a temporary single `branch` → `ollama_chat` that classifies one field; stdout the raw model output
- [ ] Make model name + server address env-configurable (`OLLAMA_MODEL`, `OLLAMA_ADDRESS`)
- [ ] **Security:** model runs locally (no data leaves the host); document the optional hosted-LLM path without enabling it
- [ ] **Docs:** document model choice + how to change it; note first-run pull time

**Acceptance criteria**
- [ ] `ollama-pull` completes and the model appears in `ollama list`
- [ ] The smoke-test branch returns a model response for a real edit (visible in stdout)
- [ ] Changing `OLLAMA_MODEL` in `.env` swaps the model on restart
- [ ] Connect waits for the model (no "model not found" race on cold start)

## Phase 7 — Pass-1 classification + robust output parsing

> Goal: every surviving edit gets a normalized `{label, confidence}`.

- [ ] Replace the smoke test with a real pass-1 `branch`: `request_map` builds the prompt; `ollama_chat`; `result_map` grafts result back (don't overwrite the record)
- [ ] Robust parse: extract first `{...}` block, fallback `{}` on parse failure, normalize label to the enum, default `unclear`, coerce confidence to a number
- [ ] "Retries on bad output" strategy: rely on fallback-to-`unclear` + later UPSERT correction (Phase 9) instead of an in-pipeline LLM retry loop; document the why (latency/cost vs. self-correcting convergence)
- [ ] **Security:** constrain output to the fixed enum so prompt-injection can't change behavior; result is advisory only
- [ ] **Docs:** document the pass-1 prompt and the parse/normalize rules

**Acceptance criteria**
- [ ] Records carry `label ∈ {vandalism,substantive,trivia,unclear}` and `confidence ∈ [0,1]`
- [ ] A model reply with surrounding prose (dirty JSON) still parses to a valid label
- [ ] A model reply with an out-of-enum label normalizes to `unclear`
- [ ] A malformed/empty model reply does not crash the pipeline (defaults to `unclear`)

## Phase 8 — Pass-2 confidence-based escalation

> Goal: a structured second pass for ambiguous items (real agent topology).

- [ ] Add a `switch` on `confidence < CONFIDENCE_THRESHOLD || label == "unclear"` → richer escalation `branch` (more context); reuse the robust parse; set `escalated = true`
- [ ] Make `CONFIDENCE_THRESHOLD` env-configurable
- [ ] **Security:** same enum-constraint + advisory-only guarantees apply to pass 2
- [ ] **Docs:** document why two passes (cost vs. accuracy) and when escalation triggers

**Acceptance criteria**
- [ ] High-confidence pass-1 records skip the second call (`escalated = false`)
- [ ] Low-confidence / `unclear` records trigger pass 2 and show `escalated = true`
- [ ] Lowering `CONFIDENCE_THRESHOLD` measurably reduces escalations
- [ ] Pass-2 output is also enum-normalized and crash-safe

## Phase 9 — Dual sink (topic + Postgres UPSERT) — end-to-end

> Goal: persist results durably and stream them; remove temporary stdout.

- [ ] `broker` fan-out output: Kafka topic `wiki.edits.classified` (key = `rev_id`)
- [ ] Routing decision: use ONE labeled topic (`label` column) rather than topic-per-label; the confidence `switch` (Phase 8) is the routing logic. Note this explicitly so the "route" requirement is traceable
- [ ] `sql_insert` to `classified_edits` with `ON CONFLICT (rev_id) DO UPDATE` (UPSERT); stamp `classified_at`
- [ ] Remove the temporary `stdout` output
- [ ] **Security:** DSN from env; explicit `sslmode`; confirm no creds in logs
- [ ] **Docs:** document the topic, browsing it in Console, and how UPSERT corrects cold-start rows

**Acceptance criteria**
- [ ] Fresh `docker compose up` results in the dashboard filling with live classified edits
- [ ] Messages appear on `wiki.edits.classified` in Redpanda Console (keyed by rev_id)
- [ ] Re-processing a `rev_id` updates the existing row (no PK collision, no duplicate)
- [ ] A row that lands `unclear` on first pass is corrected by a later UPSERT (no permanent stuck rows)

## Phase 10 — Automated tests (after core features)

> Goal: lock in behavior, especially the gnarly parsing/edge cases.

- [ ] App unit tests: label filter, parameterized query, JSON serialization, empty + 503 states
- [ ] Bloblang transform tests (Connect test harness): frame parse, filter, label normalization, enum-drift → `unclear`, dirty-JSON fallback, heartbeat dropped (not passed through)
- [ ] Integration smoke test: compose subset (db + app + seed) asserts `/` and `/api/edits`
- [ ] Wire all tests into the CI test job (replace the Phase 1 placeholder)
- [ ] **Security:** test asserting HTML output escapes a malicious `<script>` title/comment
- [ ] **Docs:** README "Testing" section — how to run locally and what's covered

**Acceptance criteria**
- [ ] `pytest` + Connect transform tests pass locally and in CI
- [ ] Tests cover each edge case above with at least one assertion
- [ ] CI fails if any test fails (verified by a temporary deliberate break, then reverted)

## Phase 11 — Observability & hardening

> Goal: useful logs and resilient startup/runtime defaults.

- [ ] Tune Connect logger (level/format) for useful, non-spammy logs
- [ ] Add retry/backoff + batching on Connect outputs; healthcheck-gated `depends_on` across services
- [ ] Add a basic metrics/counter view or `/healthz` summary (classified count, unclear rate)
- [ ] **Security:** dependency pin audit; confirm services bind localhost-only by default
- [ ] **Docs:** ports table + troubleshooting section in README

**Acceptance criteria**
- [ ] Logs clearly show ingest → classify → sink activity without flooding
- [ ] Transient Postgres/Ollama unavailability is retried, not fatal (kill+restart test)
- [ ] `/healthz` (or metrics view) reports a live classified count and unclear rate

## Phase 12 — Required write-up & final repro polish (deliverable)

> Goal: the graded README write-up and a clean one-command repro.

- [ ] README **Tradeoffs** section — write up these two committed pairs (name the alternative + when you'd flip + what shaped the thinking):
  - [ ] Pair A: **one classification call vs. multi-step reasoning loop** (we built the loop: pass-1 + confidence escalation)
  - [ ] Pair B: **Connect as the sink vs. app-side writes from a topic** (we chose Connect `sql_insert` UPSERT)
- [ ] README **Surprises** paragraph + **"where this breaks in production"** paragraph
- [ ] README final polish: copy-pasteable run, architecture diagram, ports table
- [ ] **Security:** final pass — `gitleaks` clean on full history; localhost-only noted; all deps pinned
- [ ] **Docs:** ensure `.env.example` is complete and every documented step is reproducible from a fresh clone

**Acceptance criteria**
- [ ] A teammate following only the README reaches visible classified edits from a fresh clone
- [ ] Tradeoffs section names alternatives + flip conditions (not boilerplate)
- [ ] Surprises + production-failure paragraphs are present and specific
- [ ] `docker compose up` is the only required command (no forgotten manual steps)

---

## Out of scope (tracked, not built — see PRD)
- [ ] Cloud/production deployment, multi-node Redpanda, managed Postgres
- [ ] AuthN/AuthZ + multi-user accounts on the dashboard
- [ ] Full observability stack (metrics/dashboards/alerting beyond logs)
- [ ] Hosted LLM as default; automated moderation actions; historical backfill
- [ ] Multi-source ingestion (HN / USGS / GitHub)

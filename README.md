# Wikipedia Edit-Triage Agent

[![CI](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml/badge.svg)](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml)

A locally-runnable system that ingests the Wikipedia recent-changes firehose,
triages each edit with a multi-step LLM reasoning loop (Redpanda Connect +
Ollama), and serves the results on a live dashboard. Built for the Redpanda
Field Deployed Engineer build exercise.

> Status: **Phase 6** — a Redpanda Connect pipeline ingests and transforms the
> live Wikipedia firehose, fetches each edit's real diff, and classifies it with
> a local Ollama model (pass-1 `{label, confidence}`) plus a confidence-based
> escalation pass for ambiguous edits — currently to stdout; the dashboard still
> serves seeded Postgres rows. The topic/UPSERT sink lands in Phase 7 (see
> [`docs/TODO.md`](docs/TODO.md)).

## Run

```bash
docker compose up
```

This starts Postgres (schema + seed applied automatically on first run), the
web app, and the `connect` ingest pipeline. Open <http://localhost:8080> to see
the triage dashboard, served from the seeded rows in [`db/seed.sql`](db/seed.sql).

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

## Pipeline (ingest + transform)

The `connect` service runs a [Redpanda Connect](https://docs.redpanda.com/redpanda-connect/)
pipeline ([`connect/wikipedia.yaml`](connect/wikipedia.yaml)) that ingests the
Wikipedia [recent-changes SSE firehose](https://stream.wikimedia.org/v2/stream/recentchange)
and transforms it into a clean, model-ready schema. Watch it live:

```bash
docker compose logs -f connect   # streams one clean JSON edit per line
```

Key choices:

- **Source / SSE in Connect.** Consumed with `http_client` + `stream.enabled` +
  the `lines` scanner. SSE frames look like `data: {…}`; we keep only `data:`
  lines, strip the prefix, and `parse_json().catch(deleted())` so heartbeats
  (`:ok`) and any non-JSON **fail closed** rather than passing through as raw
  strings.
- **Required `User-Agent`.** Wikipedia returns 403 without a descriptive UA; set
  via `WIKI_USER_AGENT` (a default is in `docker-compose.yml`).
- **Filter before the model.** We drop bots, non-`edit` events, and non-article
  namespaces, and scope to **English Wikipedia** (`server_name ==
  "en.wikipedia.org"`) — the firehose is *all* Wikimedia projects, and
  Wikidata/Wiktionary edits aren't meaningful to a vandalism/substantive/trivia
  classifier. Filtering here keeps the (later) LLM call volume bounded.
- **Clean schema.** Projects `rev_id, title, editor, comment, size_delta, uri,
  event_ts`; `size_delta = length.new - length.old`; the epoch `timestamp` is
  formatted to an ISO-8601 string (TIMESTAMPTZ-safe), falling back to `meta.dt`.

The pipeline currently sinks to **stdout** only; the topic + Postgres UPSERT
sink arrives in Phase 7. Dedup is deferred to the Postgres `rev_id` UPSERT (an
SSE stream rarely re-sends a `rev_id`; reconnect replays are absorbed by the
UPSERT), so no in-pipeline cache is needed.

## Classification (diff-enriched, two-pass)

Each surviving edit is enriched with its **actual diff** and classified by a
**local Ollama model** through Connect `branch`es (in
[`connect/wikipedia.yaml`](connect/wikipedia.yaml)). The dashboard isn't wired to
these results yet (that's the Phase 7 sink) — watch them on stdout:

```bash
docker compose logs -f connect   # each line carries label + confidence + escalated
```

How it works:

- **Fetch the real diff (the actual evidence).** The recentchange SSE event is
  only edit *metadata* (title, comment, size delta) — never the changed text. A
  `branch` fetches each edit's diff from the MediaWiki REST compare API
  (`/w/rest.php/v1/revision/{from}/compare/{to}`, keyed off the event's parent
  and new revision ids), keeps only the changed lines (`+ added` / `- removed` /
  `~ modified`, dropping unchanged context), truncates to ~4 KB, and stashes it
  in metadata so the clean record stays DB-ready. The fetch fails **closed**: a
  deleted/suppressed revision, timeout, or rate-limit yields an empty diff and
  classification still proceeds on metadata. A local rate limit (`wiki_api`,
  10/s) keeps us a polite API citizen.
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
  one-shot `ollama-pull` preloads it on startup, and `connect` waits for that to
  complete (`service_completed_successfully`) so there's no cold-start "model not
  found" race. First run downloads the model (`llama3.2`, ~2 GB), so the initial
  `docker compose up` takes a few minutes; later runs reuse the cached `ollama`
  volume.
- **Change the model.** Set `OLLAMA_MODEL` (any Ollama model name) in `.env`; it
  is pulled automatically. `OLLAMA_ADDRESS` points Connect at the server.
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

  The `connect` service already maps `host.docker.internal`, so only
  `OLLAMA_ADDRESS` needs to change. The containerized Ollama remains the default
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
connect/             # wikipedia.yaml (Redpanda Connect ingest pipeline)
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

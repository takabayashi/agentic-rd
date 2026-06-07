# Wikipedia Edit-Triage Agent — Product Requirements (PRD)

> A small, locally-runnable system that ingests the Wikipedia recent-changes
> firehose, transforms it in Redpanda Connect, runs a multi-step LLM reasoning
> loop to triage each edit, and serves the results on a live web dashboard.
>
> Built for the Redpanda **Field Deployed Engineer** build exercise.

---

## Problem Statement

Wikipedia receives a continuous, high-volume stream of edits (~50/sec via the
public recent-changes SSE feed). The vast majority are noise from a triage
perspective — bot edits, heartbeats, and non-article namespaces — while the
edits that matter (potential vandalism vs. substantive contributions) are buried
in the firehose. A human moderator cannot reasonably watch the raw stream.

The problem: **turn a noisy, real-time public firehose into a small, ranked,
human-actionable view of edits that deserve attention**, using an LLM only where
judgment is actually required (and never on records that should be filtered out
cheaply first).

This is intentionally a thin vertical slice that exercises the full path —
ingest → transform → reason → serve — runnable with a single `docker compose up`.

---

## Target Users

- **Primary: Wikipedia moderators / patrollers.** Need a fast, prioritized list
  of recent edits classified by intent so they can focus review effort on likely
  vandalism and substantive changes instead of scrolling a raw feed.
- **Secondary: the Redpanda evaluation team.** Will clone the repo, run it
  locally, and inspect the pipeline, agent topology, schema, and dashboard. A
  clean one-command start and useful logs are part of the deliverable.
- **Tertiary (illustrative): trust-and-safety / data analysts** who want a
  queryable store of recently-classified edits for ad hoc inspection.

---

## Core Features

Described from the user's perspective:

- **Live triage dashboard.** As a moderator, I see a continuously-updating table
  of recent edits, each with a triage label (`vandalism | substantive | trivia |
  unclear`), a confidence score, the article title, the editor, and a link to
  the diff — so I can act on the highest-priority items first.
- **Smart pre-filtering.** As a moderator, I only see edits worth a human's time:
  bot edits, heartbeats, and non-article namespaces are dropped before any model
  runs, so the feed (and the LLM cost) stays focused on real content edits.
- **Multi-step LLM reasoning, not one giant prompt.** As a reviewer of the
  system, I can see the agent has structure: a cheap first-pass classification,
  a confidence-based escalation pass that pulls more diff context for ambiguous
  cases, output validation, and retries on malformed model output.
- **Confidence-based prioritization & filtering.** As a moderator, I can filter
  the dashboard by label and sort by confidence, so low-confidence or
  high-risk edits surface to the top.
- **Durable, queryable history.** As an analyst, classified edits are persisted
  (Redpanda topic + Postgres) and de-duplicated/upserted, so re-processed or
  late-classified records converge to a single correct row I can query.

---

## User Flows

### Flow 1 — Moderator triages the live feed (primary)
1. Reviewer runs `docker compose up`; all services start (broker, Connect,
   Ollama, Postgres, web app).
2. Edits stream in; the pipeline filters noise and classifies survivors.
3. Moderator opens the web dashboard (e.g. `http://localhost:8080`).
4. Dashboard shows the most recent classified edits, newest first,
   auto-refreshing.
5. Moderator filters to `vandalism` and sorts by confidence descending.
6. Moderator clicks the diff link for a high-confidence item to review on
   Wikipedia and take action.

### Flow 2 — The agent reasoning loop (per edit, internal)
1. **Ingest**: edit arrives via SSE (`http_client`, `stream.enabled: true`,
   `lines` scanner); `data:` prefix is stripped; non-JSON heartbeats are dropped
   (fail-closed, not passed through as raw strings).
2. **Filter/project**: drop `bot == true`, drop non-`type=edit`, keep only the
   main article namespace (`namespace == 0`), and scope to English Wikipedia
   (`server_name == "en.wikipedia.org"`) — the firehose is all Wikimedia
   projects; project to a clean schema.
3. **Dedupe**: handled durably by the Postgres `rev_id` UPSERT (Phase 7). An SSE
   stream rarely re-sends a `rev_id` (reconnect replays are absorbed by the
   UPSERT), so no in-pipeline Connect cache is used. A Connect cache keyed on
   item id would be the right tool for a *poll-based* source (HN/GitHub), which
   refetches the same ids each poll.
4. **Classify (pass 1)**: a `branch` builds a prompt from title + comment + size
   delta; the model returns `{label, confidence}`.
5. **Confidence branch**: if `confidence < threshold` (or label is `unclear`),
   escalate — a second prompt with richer diff context re-classifies.
6. **Validate/normalize**: extract the first `{...}` block, fall back to
   `unclear` on parse failure, normalize the label to the enum
   (`.string().trim().lowercase()` + map to allowed set).
7. **Persist**: write to a Redpanda topic and UPSERT into Postgres; cold-start
   or transient model failures land as `unclear` and are corrected on a later
   pass.

### Flow 3 — Analyst queries history (secondary)
1. Analyst connects to Postgres (or consumes the topic).
2. Runs SQL over the classified-edits table (filter by label, time window,
   confidence, namespace).

---

## Technical Constraints

- **One-command local run**: `docker compose up` must bring up everything with
  no manual steps; no missing files; logs must be useful.
- **All free / local / open source.** No paid or signup-gated services.
- **Broker**: `docker.redpanda.com/redpandadata/redpanda` in
  `--mode=dev-container` (single node).
- **Pipeline**: Redpanda Connect (`docker.redpanda.com/redpandadata/connect`,
  Apache-2.0) for ingest, transform, routing, and LLM `branch` calls. The
  exercise's "route" requirement is satisfied by the confidence-based `switch`
  (route ambiguous items to the escalation pass) plus a single labeled topic
  (`label` column) — a deliberate choice over topic-per-label routing (see the
  Tradeoffs write-up).
- **LLM**: local via **Ollama** (`ollama/ollama`) with a small open-weights
  model, called through Connect's `ollama_chat` (or `openai_chat_completion`
  pointed at the Ollama server). Model name configurable via env.
- **Storage**: **both** a Redpanda topic (stream of classified edits) and
  **Postgres 16** (UPSERT sink for serving/queries).
- **Serving**: a lightweight web app reading from Postgres, rendering a plain
  but functional auto-refreshing table.
- **Data source rules**: Wikipedia SSE requires a descriptive `User-Agent`
  header (it 403s without one); timestamps are epoch and must be formatted to an
  ISO string before insertion into a `TIMESTAMPTZ` column.
- **Off-limits** (per exercise): Redpanda Cloud, Enterprise Connect connectors
  (CDC, Snowflake Streaming, Iceberg, Salesforce), `a2a_message`, Cloud OAuth2.
- **Config via env**: model name, confidence threshold, DB credentials, and
  User-Agent provided via `.env` / `docker-compose` (a `.env.example` is
  included even though the default LLM is local).
- **Infrastructure/deployment**: runtime scoped to local Docker Compose for this
  exercise (see Out of Scope for production/cloud deployment). A *minimal* CI
  (lint, build, tests, secret-scan) keeps the repo trustworthy and is kept small
  on purpose; the brief doesn't ask for CI, so deploy automation, dependency
  bots, and extra linters are out of scope and not expanded.
- **Scope discipline ("plain but works")**: the brief is an explicit
  couple-of-hours exercise graded on judgment, not surface area. Build exactly
  the evaluated path — ingest → transform → reason → serve — with a plain,
  functional UI; avoid gold-plating (elaborate UI, metrics stacks, deploy
  pipelines). Every cut is recorded in Out of Scope with a reason.

---

## Security Considerations

- **No committed secrets.** Any credentials (DB password, optional hosted-LLM
  keys) come from `.env`; `.env.example` is committed, `.env` is gitignored.
- **Required `User-Agent`.** Send a descriptive UA on the Wikipedia request, per
  their policy, to avoid 403s and be a good API citizen.
- **Untrusted input → prompt-injection awareness.** Edit comments and titles are
  attacker-controllable free text fed into the LLM. Treat model output as data
  only (a label + confidence), never as instructions or executable content;
  constrain/parse output to a fixed enum so injected instructions can't change
  system behavior.
- **Output is non-authoritative.** Classifications are advisory; the system takes
  no automated moderation action, limiting blast radius of a wrong/poisoned call.
- **Local-only surface.** Default deployment binds services to localhost; no
  inbound auth is implemented because nothing is exposed publicly (revisit if
  ever deployed — see Out of Scope).

---

## Error Handling & Edge Cases

These are first-class requirements, not afterthoughts (the firehose makes them
the core of the work):

- **Non-JSON heartbeats**: must be dropped fail-closed; never passed downstream
  as raw strings (use `.catch(deleted())`, do not rely on `if` to fail closed).
- **Bloblang root rebuild**: start mappings from `root = this` (or fold fields)
  so a trailing single-field assignment doesn't wipe the record; inside
  `branch.result_map`, partial `root.X = ...` is correct (branch grafts back in).
- **branch for LLM calls**: `request_map` builds the prompt, `result_map` grafts
  the result back; never overwrite the original message with the raw model
  response.
- **Dirty model JSON**: extract the first `{...}` block; on parse failure fall
  back to a default label (`unclear`); normalize labels to the enum to handle
  model drift outside the allowed set.
- **Cold-start / transient LLM failure**: rows can pass through `branch`
  unclassified on the first poll — pair with an **UPSERT sink** so a later pass
  corrects them.
- **Retries on bad output**: handled via **fallback-to-`unclear` + UPSERT
  correction**, not an in-pipeline LLM retry loop. Rationale: on a noisy
  firehose, blocking/retrying a synchronous model call adds latency and cost for
  marginal gain, whereas a cheap default plus a self-correcting later pass keeps
  throughput bounded and converges to the right label. (Would flip toward
  explicit retries if classifications were authoritative/irreversible.)
- **Dedupe**: re-emitted/replayed records are deduped durably by the Postgres
  `rev_id` UPSERT (primary key), preventing duplicate rows and PK collisions. No
  in-pipeline cache for this SSE source; a Connect cache keyed on item id would
  be added for a poll-based source that refetches the same ids.
- **Timestamp conversion**: epoch → ISO string in Bloblang before writing to
  `TIMESTAMPTZ`.
- **Backpressure / volume**: ~50 edits/sec firehose; filtering happens *before*
  the model so LLM call volume stays bounded; batching and retry/backoff
  configured on Connect outputs and the LLM `branch`.
- **Service startup ordering**: web app and Connect tolerate Postgres/Ollama not
  being ready yet (retries / healthchecks) so `docker compose up` is robust.

---

## Success Metrics

- **One-command repro**: a clean checkout runs end-to-end with `docker compose
  up` and produces visible classified edits within a short bootstrap window.
- **Freshness/latency**: median time from edit ingestion to dashboard visibility
  is on the order of seconds, not minutes.
- **Classification coverage**: high percentage of surviving (post-filter) edits
  end up with a non-`unclear` label after the escalation pass; `unclear` rows
  trend down as later passes upsert corrections.
- **Filter effectiveness**: large reduction from raw firehose volume to
  model-eligible records (bots/heartbeats/non-article dropped), keeping LLM call
  rate bounded.
- **Robustness**: no pipeline crash on malformed/heartbeat records over a
  sustained run; no PK collisions; no unclassified rows left permanently stuck.
- **Usability**: a reviewer can, within seconds of opening the dashboard,
  identify and open the highest-confidence likely-vandalism edits.

---

## Out of Scope (for this exercise)

Deliberately excluded to stay within the intended ~couple-hours build; listed as
future work:

- **Cloud / production deployment**, autoscaling, multi-node Redpanda, managed
  Postgres, secrets manager.
- **CI/CD expansion** beyond the minimal lint/build/test/secret-scan: image
  publishing/deploy automation, dependency bots, branch protection, extra
  Dockerfile/YAML linters — the brief doesn't ask for CI.
- **AuthN/AuthZ** on the dashboard/API and multi-user accounts.
- **Observability stack** (metrics/dashboards/alerting beyond container logs);
  only output retries/backoff + useful logs are in scope.
- **Hosted LLM** as the default (local Ollama is primary; hosted left as an
  optional config path via `.env.example`).
- **Automated moderation actions** (reverting edits, notifications) — output is
  advisory only.
- **Historical backfill / long-term retention policies** beyond what Postgres
  holds during a run.
- **Multi-source ingestion** (HN / USGS / GitHub) — single source by design.

---

## Appendix — Proposed Tech Stack

| Piece    | Choice                                                        |
|----------|--------------------------------------------------------------|
| Broker   | Redpanda (`--mode=dev-container`, single node)               |
| Pipeline | Redpanda Connect (SSE input, Bloblang transforms, `branch`) |
| LLM      | Ollama (local, small open-weights model, configurable)       |
| Storage  | Redpanda topic + Postgres 16 (UPSERT sink)                   |
| Serving  | Lightweight web app (table dashboard reading Postgres)       |
| Run      | Docker Compose (`docker compose up`)                         |

> Open choice to confirm during build: web app implementation language/framework
> for the dashboard (kept intentionally minimal — "plain but works").

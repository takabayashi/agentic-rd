# Dashboard & API

[← Back to README](../README.md)

The web app (`webapp`, served at <http://localhost:8080>) reads classified edits
from Postgres and renders them. It never consumes Kafka directly.

- `GET /` — HTML dashboard: a table of classified edits sorted by confidence
  descending. A header stat line shows the total, the escalated count, and how
  long ago the newest row was classified. Each row links to the **article page**
  and the Wikipedia **diff** separately, shows the `#rev_id`, and a relative
  "Classified" time so you can see rows arriving live. Label-filter chips
  (`all/vandalism/substantive/trivia/unclear`) plus an **escalated** toggle
  (combinable) narrow the table. Updates are **live**: a tiny vanilla-JS poller
  (no external library, no build step) re-fetches the server-rendered `#feed`
  fragment every few seconds, swaps it in, and flashes newly-arrived rows —
  replacing the old full-page meta-refresh. A "live" dot turns grey if a poll
  fails. Rendered in plain Python (no template engine); untrusted fields (title,
  comment, editor) are escaped with `html.escape`, and links are emitted only for
  `http(s)` URIs with `rel="noopener noreferrer"`.
- `GET /fragment/edits?label=&escalated=1` — the dynamic dashboard region (stats
  + filters + table) as an HTML fragment; this is what the poller swaps in. The
  server stays the single source of markup (the client never re-implements row
  rendering).
- `GET /api/edits?label=<label>&escalated=1&limit=&offset=` — the same data as
  JSON, newest-highest-confidence first. `label` (one of
  `all|vandalism|substantive|trivia|unclear`) and `escalated=1` filter;
  `limit`/`offset` paginate; omitting them returns the whole recent window. Each
  row:

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

## Health, readiness, and metrics

```bash
curl localhost:8080/healthz   # -> 200 liveness (does NOT require the DB)
curl localhost:8080/readyz    # -> 200 when the DB is reachable, else 503
curl localhost:8080/metrics   # -> Prometheus exposition (request counts + latency)
```

`/healthz` is liveness only (so an orchestrator never restarts the app during a
cold DB start); `/readyz` is the DB-backed readiness gate. If you open the
dashboard before Postgres is ready, you get a 503 "warming up" page that
auto-retries — the app never crashes on a cold or transient DB. See
[`observability.md`](observability.md) for the metrics and logging details.

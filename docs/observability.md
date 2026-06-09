# Observability

[← Back to README](../README.md)

Lightweight, local, no external stack required:

- **App metrics** — `GET /metrics` on the dashboard exposes Prometheus request
  counts + latency (labelled by method, route template, status). Instrumented by
  a small ASGI middleware ([`app/triage/metrics.py`](../app/triage/metrics.py)).
- **Pipeline metrics** — each Connect service serves Prometheus metrics on `:4195`
  (`metrics: { prometheus: {} }`); the classify stage's port is mapped to the host
  (`http://localhost:4195/metrics`) for input/output/processor counters,
  latencies, and errors.
- **Structured logs** — the app logs one-line JSON per record
  ([`app/triage/logging_config.py`](../app/triage/logging_config.py)) for easy
  grep/aggregation; Connect logs `logfmt`.
- **Readiness** — `GET /readyz` (DB-backed) vs `GET /healthz` (liveness).

Point any Prometheus at `localhost:8080/metrics` and `localhost:4195/metrics` to
scrape the app and the classify pipeline.

# Wikipedia Edit-Triage Agent

A locally-runnable system that ingests the Wikipedia recent-changes firehose,
triages each edit with a multi-step LLM reasoning loop (Redpanda Connect +
Ollama), and serves the results on a live dashboard. Built for the Redpanda
Field Deployed Engineer build exercise.

> Status: **Phase 0** — project skeleton. The web app starts cleanly and serves
> a health endpoint. Ingest, transform, LLM, and dashboard land in later phases
> (see [`docs/TODO.md`](docs/TODO.md)).

## Run

```bash
docker compose up
```

Then open <http://localhost:8080>. You should see `{"status": "ok"}`.

Health check:

```bash
curl localhost:8080/healthz   # -> HTTP 200
```

## Develop / test

```bash
cd app
pip install -r requirements.txt
pytest
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed. `.env` is gitignored — no
secrets are committed. Phase 0 requires no configuration.

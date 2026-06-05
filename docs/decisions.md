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

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

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

## Planning — Scope revalidation against the brief

### Consolidate the build plan (13 phases → 10) and cap scope
- **Decision:** Revalidated `requirements.md` + `TODO.md` against the take-home brief and trimmed for the explicit "couple-of-hours / plain but works" framing. Merged Connect ingest + transform (now Phase 4), merged Ollama infra + pass-1 classify (Phase 5), and folded the standalone "observability" phase's useful parts (output retries/backoff + clean logs) into the end-to-end dual-sink phase (Phase 7) while dropping the metrics/counter view. Trimmed UI and test scope. Kept the required README write-up as its own final phase (Phase 9) because it is the most heavily graded artifact.
- **Alternatives:** Keep the granular 13-phase plan; cut Postgres and serve only a topic; drop the second LLM pass.
- **Rationale / trade-offs:** The brief grades judgment and "names the cuts", not surface area, and warns against gold-plating. The consolidated plan still covers every asked deliverable (ingest → transform → reason → serve, README write-up, one-command run) and every evaluation dimension (connector fluency incl. retries/error paths, data sense, multi-step agent design, output usability, local repro, architectural reasoning). Dual sink (topic + Postgres) is kept deliberately because it directly feeds two of the brief's Tradeoffs pairs. We gave up granular per-step verifiability for a leaner, more honest plan.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Cap CI/CD at the minimal setup already in place
- **Decision:** Treat the existing lint/test/build/secret-scan CI as sufficient and do **not** expand CI/CD. GHCR deploy (`deploy.yml`), Dependabot, branch protection, and the hadolint/yamllint jobs are reframed as extras beyond the brief (kept since already built, but not grown); recorded under Out of Scope.
- **Alternatives:** Continue building out CI/CD (more linters, environments, release automation); or delete the already-built deploy/Dependabot config entirely.
- **Rationale / trade-offs:** The brief never asks for CI; over-investing there spends the "couple of hours" away from the graded ingest→reason→serve path. Keeping the built pieces avoids churn/regressions; not expanding them avoids gold-plating. Deleting them was rejected as needless rework with no scoring upside. Supersedes the implied "CI is a first-class scope area" stance from the Phase 1 entries above.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

### Remove `deploy.yml` + `dependabot.yml` (supersedes the two entries above)
- **Decision:** Deleted `.github/workflows/deploy.yml` (GHCR publish) and `.github/dependabot.yml`. CI is now just `ci.yml` (lint/test/build/secret-scan). Supersedes the "Deploy: publish to GHCR" entry and the "kept since already built" stance of the cap-CI entry.
- **Alternatives:** Keep them dormant (prior decision).
- **Rationale / trade-offs:** Human chose a leaner, brief-aligned repo footprint. The deploy/dependabot config carried maintenance surface (version bumps, token scopes) for zero scoring upside on a local-run exercise. Trade-off: a future real deployment re-adds a release workflow, but that's out of scope here.
- **Made by:** Human+Agent
- **Date:** 2026-06-07

## Phase 2 — Dashboard with mocked data

### Server-rendered Jinja2 dashboard (not a client-side SPA)
- **Decision:** Render `/` server-side with Jinja2 templates; auto-refresh via a plain `<meta http-equiv="refresh">`. A parallel `GET /api/edits` returns JSON.
- **Alternatives:** React/Vue SPA fetching the JSON API; HTMX partial updates; websockets/SSE push.
- **Rationale / trade-offs:** The brief wants "plain but works" and a result a person can act on. Server rendering needs no build step, ships in the existing FastAPI image, and is trivially testable via the test client. Meta-refresh is cruder than HTMX/websockets but adequate for a seconds-fresh triage feed. The JSON endpoint keeps a clean seam for a richer UI later. Autoescaping (on by default) is load-bearing here because titles/comments are attacker-controlled.
- **Made by:** Agent
- **Date:** 2026-06-07

### Pydantic `EditView` as the single view-model + `load_edits()` data seam
- **Decision:** Define one pydantic `EditView` (+ `Label` enum) in `models.py` as the contract for both the HTML view and the JSON API; the web layer pulls data through `mock_data.load_edits()`, a thin seam Phase 3 swaps for a Postgres repository without touching routes.
- **Alternatives:** Return raw dicts/ORM rows to the template; query the data source directly inside the route handlers.
- **Rationale / trade-offs:** One typed contract keeps the UI, API, and (later) the DB schema in agreement and gives free, correct JSON serialization (datetimes → ISO, enum → value), pre-satisfying the pipeline's "epoch → ISO" rule at the serving edge. The `load_edits()` indirection is a deliberate, minimal seam (not a speculative repository interface) so the mock→Postgres swap is a one-module change. Cost: a little ceremony for what is still a single table.
- **Made by:** Agent
- **Date:** 2026-06-07

# Wikipedia Edit-Triage Agent

[![CI](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml/badge.svg)](https://github.com/takabayashi/agentic-rd/actions/workflows/ci.yml)

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

## CI/CD

Every push and pull request runs GitHub Actions
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) with least-privilege
`GITHUB_TOKEN` permissions (`contents: read`). Jobs:

| Job        | What it checks                                              |
|------------|------------------------------------------------------------|
| `lint`     | `ruff check` + `ruff format --check` (config: `ruff.toml`) |
| `yamllint` | YAML style (config: `.yamllint.yml`)                       |
| `hadolint` | `app/Dockerfile` best practices                            |
| `test`     | `pytest` (the Phase 0 health tests)                        |
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

**Dependency hygiene.** [Dependabot](.github/dependabot.yml) opens weekly update
PRs for pip deps, the Docker base image, and the pinned GitHub Actions.

**Deploy.** Pushing a version tag publishes the webapp image to GHCR
([`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)):

```bash
git tag v0.1.0 && git push origin v0.1.0
# -> ghcr.io/takabayashi/agentic-rd-webapp:0.1.0
```

Manual fallback (no tag needed):

```bash
docker compose build
docker tag agentic-rd-webapp:0.0.0 ghcr.io/takabayashi/agentic-rd-webapp:manual
echo "$GHCR_PAT" | docker login ghcr.io -u takabayashi --password-stdin
docker push ghcr.io/takabayashi/agentic-rd-webapp:manual
```

**Branch protection (expected).** Protect `main` to require the CI checks above
to pass before merge, and disallow direct pushes so every change flows through a
reviewed PR.

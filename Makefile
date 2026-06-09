# Developer convenience targets for the Wikipedia edit-triage agent.
# `make` or `make help` lists everything. Service targets wrap docker compose;
# OLLAMA_ADDRESS is read from .env (set it to http://host.docker.internal:11434
# to use a host-native Ollama on macOS/Colima).

COMPOSE       ?= docker compose
CONNECT_IMAGE ?= docker.redpanda.com/redpandadata/connect:4.95.0
APP_DIR       ?= app
# Optional confidence threshold override, e.g. `make restart-connect THRESHOLD=0.95`.
THRESHOLD     ?=

.DEFAULT_GOAL := help
.PHONY: help up up-fg down down-v restart restart-connect restart-webapp ps build \
        logs logs-connect diffs labels escalations errors psql ollama-check \
        topics consume-classified consume-audit console open health \
        install test lint fmt yamllint connect-lint check

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## --- Services ---

up: ## Start all services in the background
	$(COMPOSE) up -d

up-fg: ## Start all services in the foreground (Ctrl-C to stop)
	$(COMPOSE) up

down: ## Stop and remove containers
	$(COMPOSE) down

down-v: ## Stop and remove containers + volumes (re-seeds Postgres on next up)
	$(COMPOSE) down -v

restart: down up ## Recreate the whole stack

restart-connect: ## Recreate just the connect pipeline (THRESHOLD=0.95 to override)
	$(if $(THRESHOLD),CONFIDENCE_THRESHOLD=$(THRESHOLD)) $(COMPOSE) up -d --force-recreate connect

restart-webapp: ## Recreate just the web app
	$(COMPOSE) up -d --force-recreate webapp

ps: ## Show service status
	$(COMPOSE) ps

build: ## Build images
	$(COMPOSE) build

## --- Logs & pipeline observability ---

logs: ## Follow all service logs
	$(COMPOSE) logs -f

logs-connect: ## Follow the connect pipeline logs
	$(COMPOSE) logs -f connect

diffs: ## Show recent diff-fetch log lines (rev_id + diff_chars)
	@$(COMPOSE) logs connect 2>/dev/null | grep "diff fetched" | tail -20

labels: ## Show the classification label distribution
	@$(COMPOSE) logs connect 2>/dev/null | grep -oE '"label":"[a-z]+"' | sort | uniq -c

escalations: ## Count escalated true/false in the connect logs
	@printf 'escalated:true  = %s\n' "$$($(COMPOSE) logs connect 2>/dev/null | grep -oc '"escalated":true')"
	@printf 'escalated:false = %s\n' "$$($(COMPOSE) logs connect 2>/dev/null | grep -oc '"escalated":false')"

errors: ## Show connect errors (e.g. null-switch crashes); expect none
	@$(COMPOSE) logs connect 2>/dev/null | grep "level=error" | tail -20 || echo "(no errors)"

psql: ## Open a psql shell on Postgres
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-wiki} -d $${POSTGRES_DB:-wiki}

ollama-check: ## Verify a reachable Ollama (host or container)
	@curl -fsS $${OLLAMA_HOST:-http://localhost:11434}/api/tags >/dev/null \
		&& echo "ollama reachable" \
		|| echo "ollama NOT reachable - run 'ollama serve' (host) or check the container"

health: ## Service status + redpanda OOM/state (the Phase 7 gotcha)
	@$(COMPOSE) ps
	@docker inspect agentic-rd-redpanda-1 --format 'redpanda: OOMKilled={{.State.OOMKilled}} status={{.State.Status}}' 2>/dev/null || true

open: ## Open the dashboard (http://localhost:8080) in the browser
	@open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null || echo "open http://localhost:8080"

console: ## Open Redpanda Console (http://localhost:8090) in the browser
	@open http://localhost:8090 2>/dev/null || xdg-open http://localhost:8090 2>/dev/null || echo "open http://localhost:8090"

## --- Topics & broker ---

topics: ## List Redpanda topics
	$(COMPOSE) exec redpanda rpk topic list

consume-classified: ## Consume from wiki.edits.classified (N=5 to override count)
	$(COMPOSE) exec redpanda rpk topic consume wiki.edits.classified --num $(or $(N),5)

consume-audit: ## Consume from model.audit (N=3 to override count)
	$(COMPOSE) exec redpanda rpk topic consume model.audit --num $(or $(N),3)

## --- Quality & tests ---

install: ## Install app + dev Python deps (run inside your virtualenv)
	pip install -r requirements-dev.txt
	pip install -r $(APP_DIR)/requirements.txt

test: ## Run the app test suite (pytest)
	cd $(APP_DIR) && pytest -q

lint: ## Ruff lint + format check
	ruff check .
	ruff format --check .

fmt: ## Apply ruff formatting
	ruff format .

yamllint: ## Lint YAML files
	yamllint .

connect-lint: ## Validate the Connect pipeline config
	docker run --rm -e WIKI_USER_AGENT=lint -e OLLAMA_ADDRESS=http://localhost:11434 -e OLLAMA_MODEL=llama3.2 \
		-v "$(CURDIR)/connect/wikipedia.yaml:/c.yaml:ro" $(CONNECT_IMAGE) lint /c.yaml

check: lint yamllint connect-lint test ## Run all local checks (mirrors CI, minus build/gitleaks)
	@echo "All checks passed."

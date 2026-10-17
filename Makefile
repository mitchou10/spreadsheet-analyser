# =============================================================================
# spreadsheet-analyser — developer entrypoint
#
# `make` (or `make help`) lists every target grouped by topic.
# =============================================================================

UV   := uv
PNPM := pnpm
DOCKER_COMPOSE := docker compose
FRONTEND_DIR := frontend
BACKEND_DIR  := backend
AGENT_WORKER_DIR    := agent-worker
ANALYSIS_WORKER_DIR := analysis-worker
INDEX_WORKER_DIR    := index-worker

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"} \
		/^## / { printf "\n%s\n", substr($$0, 4) } \
		/^[a-zA-Z0-9_.-]+:.*##/ { printf "  %-24s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

## ▸ Setup
.PHONY: install
install: ## Install all service dependencies
	cd $(FRONTEND_DIR) && $(PNPM) install --frozen-lockfile
	cd $(BACKEND_DIR) && $(UV) sync --group dev
	cd $(AGENT_WORKER_DIR) && $(UV) sync --group dev
	cd $(ANALYSIS_WORKER_DIR) && $(UV) sync --group dev
	cd $(INDEX_WORKER_DIR) && $(UV) sync --group dev

## ▸ Lint
.PHONY: lint
lint: ## Lint every service
	cd $(FRONTEND_DIR) && $(PNPM) run typecheck
	cd $(BACKEND_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd $(AGENT_WORKER_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd $(ANALYSIS_WORKER_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd $(INDEX_WORKER_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .
	diff -r -x __pycache__ $(AGENT_WORKER_DIR)/app/search $(INDEX_WORKER_DIR)/app/search

## ▸ Test
.PHONY: test
test: ## Run every service's test suite
	cd $(BACKEND_DIR) && $(UV) run pytest
	cd $(AGENT_WORKER_DIR) && $(UV) run pytest
	cd $(ANALYSIS_WORKER_DIR) && $(UV) run pytest
	cd $(INDEX_WORKER_DIR) && $(UV) run pytest

## ▸ Local stack
.PHONY: up
up: ## Start the local stack with docker compose
	$(DOCKER_COMPOSE) up --build

.PHONY: down
down: ## Stop the local stack
	$(DOCKER_COMPOSE) down

## ▸ Database
.PHONY: erd
erd: ## Regenerate docs/data-model.{er,png,svg} from the SQLAlchemy models (needs graphviz)
	cd $(BACKEND_DIR) && $(UV) run python scripts/generate_erd.py

.PHONY: e2e
e2e: ## Smoke-test the running stack end to end (login, collections, upload, sharing, chat); needs `make up`
	cd $(BACKEND_DIR) && $(UV) run python scripts/e2e_smoke.py

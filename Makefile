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
WORKER_DIR   := worker

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
	cd $(WORKER_DIR) && $(UV) sync --group dev

## ▸ Lint
.PHONY: lint
lint: ## Lint every service
	cd $(FRONTEND_DIR) && $(PNPM) run typecheck
	cd $(BACKEND_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd $(WORKER_DIR) && $(UV) run ruff check . && $(UV) run ruff format --check .

## ▸ Test
.PHONY: test
test: ## Run every service's test suite
	cd $(BACKEND_DIR) && $(UV) run pytest
	cd $(WORKER_DIR) && $(UV) run pytest

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

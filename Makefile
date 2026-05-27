# =============================================================================
# EchoMind — Makefile root
#
# Interfaccia unica per developer. Convenzione: ogni comando "comune" è qui,
# così non serve ricordare flag specifici di uv/docker/ruff.
#
# Self-documenting: `make help` legge i commenti `## ...` accanto ai target.
# =============================================================================

# Shell esplicita (alcuni sistemi default a /bin/sh che non supporta `set -o pipefail`)
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Compose file path (relativo alla root del repo)
COMPOSE := docker compose -f infra/docker-compose.dev.yml --env-file .env

# Colori per output leggibile (disattivabili: NO_COLOR=1 make ...)
ifndef NO_COLOR
	BLUE   := \033[34m
	GREEN  := \033[32m
	YELLOW := \033[33m
	RESET  := \033[0m
endif

# Target di default: mostra help se invocato senza argomenti. 
# Senza questa riga, eseguirebbe il primo target del file.
.DEFAULT_GOAL := help

# Tutti i target sono "phony" (non producono file con quel nome)
.PHONY: help install dev verify lint format typecheck test test-cov \
        infra-up infra-down infra-logs infra-ps infra-reset \
        precommit-install precommit-run check-env clean \
        migrate migrate-down migration migrate-history serve

# -----------------------------------------------------------------------------
# Help auto-generato
# -----------------------------------------------------------------------------
help: ## Mostra questo messaggio
	@printf "$(BLUE)EchoMind — comandi disponibili$(RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} \
	     /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' \
	     $(MAKEFILE_LIST)
	@printf "\n$(YELLOW)Suggerimento:$(RESET) lancia 'make check-env' come primo step su una macchina nuova.\n"

# -----------------------------------------------------------------------------
# Setup & Install
# -----------------------------------------------------------------------------
check-env: ## Verifica che host abbia docker, uv, python>=3.12
	@./scripts/check_env.sh

install: ## Installa tutte le dipendenze backend (runtime + dev)
	@printf "$(BLUE)→ uv sync (backend)$(RESET)\n"
	@cd backend && uv sync --all-groups

# -----------------------------------------------------------------------------
# Sviluppo quotidiano
# -----------------------------------------------------------------------------
dev: infra-up ## Avvia infrastruttura locale e mostra stato
	@printf "\n$(GREEN)✓ Ambiente di sviluppo pronto$(RESET)\n"
	@printf "  RabbitMQ UI: http://localhost:15672 (guest/guest)\n"
	@printf "  Postgres:    localhost:5432\n"
	@printf "  Redis:       localhost:6379\n"

verify: lint typecheck test ## Esegue l'intera pipeline di qualità (= ciò che CI verifica)
	@printf "\n$(GREEN)✓ verify completato$(RESET)\n"

# -----------------------------------------------------------------------------
# Qualità del codice
# -----------------------------------------------------------------------------
lint: ## Lint con ruff (check + format check)
	@printf "$(BLUE)→ ruff check$(RESET)\n"
	@cd backend && uv run ruff check .
	@printf "$(BLUE)→ ruff format --check$(RESET)\n"
	@cd backend && uv run ruff format --check .

format: ## Auto-fix di lint e formatting
	@cd backend && uv run ruff check --fix .
	@cd backend && uv run ruff format .

typecheck: ## Type checking con mypy (strict)
	@printf "$(BLUE)→ mypy$(RESET)\n"
	@cd backend && uv run mypy src tests

test: ## Esegue test pytest
	@printf "$(BLUE)→ pytest$(RESET)\n"
	@cd backend && uv run pytest

test-cov: ## Test con report coverage
	@cd backend && uv run pytest --cov --cov-report=term-missing --cov-report=html

# -----------------------------------------------------------------------------
# Infrastruttura locale (Docker Compose)
# -----------------------------------------------------------------------------
infra-up: ## Avvia Postgres + RabbitMQ + Redis in background
	@if [ ! -f .env ]; then \
		printf "$(YELLOW) .env non trovato. Copio da .env.example...$(RESET)\n"; \
		cp .env.example .env; \
	fi
	@$(COMPOSE) up -d --wait

infra-down: ## Ferma i container (mantiene i volumi)
	@$(COMPOSE) down

infra-reset: ## Ferma e rimuove ANCHE i volumi (perdita dati locali!)
	@printf "$(YELLOW) Questo elimina tutti i dati locali. Continuare? [y/N]$(RESET) "
	@read ans && [ "$$ans" = "y" ] && $(COMPOSE) down -v || echo "annullato"

infra-logs: ## Segue i log dei container
	@$(COMPOSE) logs -f --tail=100

infra-ps: ## Stato dei container
	@$(COMPOSE) ps

# -----------------------------------------------------------------------------
# Pre-commit
# -----------------------------------------------------------------------------
precommit-install: ## Installa hook pre-commit nel repo locale
	@cd backend && uv run pre-commit install --install-hooks

precommit-run: ## Esegue manualmente tutti gli hook su tutti i file
	@cd backend && uv run pre-commit run --all-files

# -----------------------------------------------------------------------------
# Database migrations (Alembic)
# -----------------------------------------------------------------------------
migrate: ## Applica tutte le migration pendenti al DB locale
	@printf "$(BLUE)-> alembic upgrade head$(RESET)\n"
	@cd backend && uv run alembic upgrade head

migrate-down: ## Rollback dell'ultima migration
	@printf "$(YELLOW) Rollback ultima migration$(RESET)\n"
	@cd backend && uv run alembic downgrade -1

migrate-history: ## Mostra la cronologia delle migration
	@cd backend && uv run alembic history --verbose

migration: ## Crea una nuova migration vuota (uso: make migration MSG="add_email_field")
	@if [ -z "$(MSG)" ]; then \
		printf "$(YELLOW)Usage: make migration MSG=\"short_description\"$(RESET)\n"; exit 1; \
	fi
	@cd backend && uv run alembic revision -m "$(MSG)"

# -----------------------------------------------------------------------------
# Server di sviluppo
# -----------------------------------------------------------------------------
serve: ## Avvia uvicorn con hot-reload (Ctrl+C per fermare)
	@printf "$(BLUE)-> uvicorn echomind.main:create_app --factory --reload$(RESET)\n"
	@cd backend && uv run uvicorn echomind.main:create_app --factory --reload --host 0.0.0.0 --port 8000

# -----------------------------------------------------------------------------
# Pulizia
# -----------------------------------------------------------------------------
clean: ## Rimuove cache di test, build artifacts, __pycache__
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	@find . -type d -name '.mypy_cache' -prune -exec rm -rf {} +
	@find . -type d -name '.ruff_cache' -prune -exec rm -rf {} +
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	@rm -rf backend/dist backend/build backend/htmlcov backend/.coverage
	@printf "$(GREEN) pulizia completata$(RESET)\n"

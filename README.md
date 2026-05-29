# EchoMind

> GraphRAG application that transforms documents and audio into **interactive knowledge graphs** and multi-level summaries.

EchoMind ingerisce testi o registrazioni audio, ne estrae automaticamente i concetti e le relazioni, costruisce un grafo navigabile e permette di interrogare il contenuto in linguaggio naturale.

## Documentazione

- [`docs/adr/`](docs/adr/) — Architectural Decision Records

## Stato attuale

**M2 — Content Ingestion** completata. M0 (project foundation) e M1 (identity & persistence) già mergiate in `develop`.

## Quick start

### Prerequisiti host

- Python ≥ **3.12**
- [`uv`](https://docs.astral.sh/uv/) ≥ 0.4
- Docker Desktop con Compose v2
- GNU Make

Verifica automatica:

```bash
make check-env
```

### Setup primo avvio

```bash
# 1. Installa dipendenze backend
make install

# 2. Installa hook pre-commit (eseguiti localmente prima di ogni commit)
make precommit-install

# 3. Copia il template variabili e popola con i valori reali
cp .env.example .env
# (modifica .env con i tuoi secret cloud — non lo committare)

# 4. Avvia infrastruttura locale (Postgres + RabbitMQ + Redis)
make dev

# 5. Applica le migration Alembic
make migrate

# 6. Avvia uvicorn con hot-reload
make serve
```

UI utili dopo `make dev`:
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Postgres**: `localhost:5432` (echomind / echomind_dev)
- **Redis**: `localhost:6379`

### Pipeline di qualità

```bash
make verify    # lint + format + typecheck + test (= ciò che CI verifica)
make format    # auto-fix di lint e formatting
make test      # solo pytest
```

Tutti i comandi:

```bash
make help
```

## Struttura repository

```
EchoMind/
├── backend/              # FastAPI + Celery (Python)
│   ├── pyproject.toml
│   ├── src/echomind/
│   ├── alembic/
│   └── tests/
├── frontend/             # React + Vite (placeholder, scaffolding in M6)
├── infra/
│   ├── docker-compose.dev.yml
│   └── postgres-init/    # script di bootstrap ruoli Postgres
├── docs/
│   └── adr/              # Architectural Decision Records
├── scripts/
│   ├── check_env.sh
│   └── check_no_real_secrets_in_tests.py
├── .github/workflows/    # CI GitHub Actions
├── .env.example          # template variabili (committato; .env reale escluso)
├── .gitleaks.toml        # config gitleaks per scan secrets
└── Makefile              # interfaccia developer
```

## Workflow di sviluppo

1. **Branch dedicato per ogni feature**: `feature/<nome-feature>` (a partire da `develop`)
2. **Plan prima del codice**: per task non triviali, scrivere un piano breve (target file, sequenza, trade-off) prima dell'implementazione
3. **Pre-commit hooks** intercettano errori prima del push (ruff, mypy, gitleaks, custom secret scanner)
4. **CI obbligatoria** prima del merge in `main`/`develop` (lint + typecheck + test integration con Postgres + secrets scan)
5. **ADR** per ogni decisione architetturale significativa (vedi [`docs/adr/`](docs/adr/))

## Licenza

[MIT](LICENSE) © 2026 Riccardo Catervi

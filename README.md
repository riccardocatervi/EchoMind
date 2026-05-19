# EchoMind

> AI-Powered GraphRAG: trasforma documenti e audio in **knowledge graph interattivi** e riassunti multilivello.

EchoMind ingerisce testi o registrazioni audio, ne estrae automaticamente i concetti e le relazioni, costruisce un grafo navigabile e permette di interrogare il contenuto in linguaggio naturale.

## Documentazione

- [`CLAUDE.md`](CLAUDE.md) — visione del progetto, stack architetturale, operating rules
- [`docs/architecture-phase0.md`](docs/architecture-phase0.md) — analisi completa, milestone, risk register
- [`docs/adr/`](docs/adr/) — Architectural Decision Records

## Stato attuale

**M0 — Project Foundation** (in corso). Solo scaffolding e tooling. Niente codice applicativo. Vedi roadmap milestone in [`architecture-phase0.md`](docs/architecture-phase0.md#4-milestone-alto-livello).

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
│   └── tests/
├── frontend/             # React + Vite (placeholder, scaffolding in M6)
├── infra/
│   └── docker-compose.dev.yml
├── docs/
│   ├── architecture-phase0.md
│   └── adr/
├── scripts/
│   └── check_env.sh
├── .github/workflows/    # CI GitHub Actions
├── .env.example          # template variabili (committato; .env reale escluso)
├── Makefile              # interfaccia developer
└── CLAUDE.md
```

## Workflow di sviluppo

1. **Branch dedicato per ogni feature**: `feature/<nome-feature>`
2. **Plan prima del codice**: per ogni task non triviale, vedi `CLAUDE.md` (Plan Mode First)
3. **Pre-commit hooks** intercettano errori prima del push
4. **CI obbligatoria** prima del merge in `main`/`develop`
5. **ADR** per ogni decisione architetturale significativa

## Licenza

[MIT](LICENSE) © 2026 Riccardo Catervi

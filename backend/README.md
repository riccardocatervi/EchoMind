# EchoMind — Backend

Servizio Python (FastAPI + Celery) per estrazione e gestione del knowledge graph.

> Per la visione e l'architettura completa, vedi [`/CLAUDE.md`](../CLAUDE.md) e [`/docs/architecture-phase0.md`](../docs/architecture-phase0.md).

## Requisiti host

- Python ≥ 3.12 (vedi [`/.python-version`](../.python-version))
- [`uv`](https://docs.astral.sh/uv/) ≥ 0.4

## Setup

Tutti i comandi vanno lanciati dalla **root del repo** tramite `make` (vedi [`/Makefile`](../Makefile)). In alternativa, manualmente:

```bash
cd backend
uv sync --all-groups       # crea .venv e installa tutto (runtime + dev)
uv run pytest              # esegue smoke test
uv run ruff check .        # lint
uv run mypy src tests      # type check
```

## Layout

```
backend/
├── pyproject.toml         # metadata + tooling config (PEP 621/735)
├── uv.lock                # lock file deterministico (committato)
├── src/echomind/          # src-layout: codice non importabile senza install
│   ├── __init__.py
│   └── _version.py
└── tests/
    └── test_smoke.py
```

## Stato attuale (M0)

Solo scaffolding: nessun endpoint, nessun modello, nessuna logica applicativa. Il primo codice arriva in **M1 — Identity & Persistence**.

# EchoMind — Backend

Servizio Python (FastAPI + Celery) per estrazione e gestione del knowledge graph.

> Per la visione e l'architettura completa, vedi [`/CLAUDE.md`](../CLAUDE.md) e [`/docs/architecture-phase0.md`](../docs/architecture-phase0.md).
> Decisioni architetturali tracciate in [`/docs/adr/`](../docs/adr/).

## Requisiti host

- Python ≥ 3.12 (vedi [`/.python-version`](../.python-version))
- [`uv`](https://docs.astral.sh/uv/) ≥ 0.4
- Docker Desktop con Compose v2 (per Postgres locale)

## Quick start (sviluppo)

Tutti i comandi vanno lanciati dalla **root del repo** tramite `make`:

```bash
# Setup primo avvio
make install            # crea .venv backend, installa runtime + dev deps
make precommit-install  # registra hook locali pre-commit
cp ../.env.example ../.env
# (poi popola .env con i secret veri — vedi sezione sotto)

# Avvio quotidiano
make dev                # avvia Postgres + RabbitMQ + Redis locali
make migrate            # applica le migration Alembic
make serve              # uvicorn con hot-reload su :8000

# Loop di sviluppo
make format             # auto-fix ruff
make verify             # lint + typecheck + test (= ciò che CI verifica)
```

Endpoint base disponibili:
- `GET  /api/v1/health` (no auth) — liveness check
- `GET  /api/v1/users/me` — claim del JWT corrente
- `GET  /api/v1/profiles/me` — profile utente (lazy create)
- `PATCH /api/v1/profiles/me` — aggiornamento parziale del profile

Documentazione interattiva: `http://localhost:8000/docs` (Swagger UI).

## Variabili d'ambiente

Tutte le variabili sono tipizzate da Pydantic Settings (`core/config.py`). Validazione cross-field a startup: l'app non parte se la combinazione è incoerente.

| Variabile | Note |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://echomind:echomind_dev@localhost:5432/echomind` per dev locale |
| `SUPABASE_JWT_ALGORITHM` | `HS256` (legacy) o `ES256` (default nuovi progetti Supabase). Vedi [ADR-0003](../docs/adr/0003-jwt-es256-support.md) |
| `SUPABASE_JWT_SECRET` | Obbligatorio se `algorithm=HS256`. Ignorato altrimenti |
| `SUPABASE_JWT_PUBLIC_KEY` | Obbligatorio se `algorithm=ES256`. Accetta PEM o JWK (JSON Web Key) su singola riga |
| `SUPABASE_JWT_AUDIENCE` | Default `authenticated` (Supabase) |

Le altre (`SUPABASE_URL`, `NEO4J_*`, `B2_*`, ...) entrano in gioco nelle milestone successive.

### HS256 (dev/test locale)

Generare un secret random:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### ES256 (Supabase reale)

Dalla dashboard Supabase → **JWT Keys → Current Key → Public Key**, copia il blocco JSON (JWK) e mettilo su singola riga in `.env`:

```env
SUPABASE_JWT_ALGORITHM=ES256
SUPABASE_JWT_PUBLIC_KEY={"keys":[{"kty":"EC","crv":"P-256","alg":"ES256","x":"...","y":"...","key_ops":["verify"]}]}
```

## Architettura layered

```
HTTP request
    ↓ FastAPI router (api/v1/*.py)
    ↓ Depends → middleware → exception handlers
    ↓ Service layer (services/*.py)        ← business logic
    ↓ Repository (db/repositories/*.py)    ← query SQL
    ↓ AsyncSession con RLS bound (db/session.py)
    ↓ PostgreSQL (con RLS enforcement)
```

Pattern di sicurezza: **doppio ruolo Postgres** (`echomind` superuser per migration, `app_runtime` non-superuser per query app). Vedi [`ADR-0002`](../docs/adr/0002-m1-auth-and-persistence.md).

## Layout

```
backend/
├── pyproject.toml                   # metadata + tooling config (PEP 621/735)
├── uv.lock                          # lock file deterministico
├── alembic.ini                      # config Alembic
├── alembic/
│   ├── env.py                       # runtime migration (async)
│   └── versions/                    # singole migration versionate
├── src/echomind/                    # src-layout
│   ├── main.py                      # FastAPI app factory + lifespan
│   ├── core/                        # config, logging, security (JWT)
│   ├── db/
│   │   ├── base.py                  # DeclarativeBase + naming convention
│   │   ├── session.py               # async engine + sessionmaker + RLS
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   └── repositories/            # query CRUD
│   ├── services/                    # business logic (API-agnostic)
│   ├── schemas/                     # Pydantic I/O schemas
│   └── api/
│       ├── deps.py                  # FastAPI dependencies
│       └── v1/                      # endpoint versione 1
└── tests/
    ├── conftest.py                  # fixture: app, client, jwt, db
    ├── test_config.py               # Pydantic Settings
    ├── test_logging.py              # structlog + context propagation
    ├── test_security.py             # JWT validation (firma, exp, aud, ...)
    ├── test_models.py               # SQLAlchemy schema dichiarato
    ├── test_health.py               # endpoint /health
    ├── test_auth.py                 # /users/me + tutti gli error code
    ├── test_profiles.py             # /profiles/me CRUD
    └── test_rls.py                  # isolamento RLS database-level
```

## Migrations

```bash
make migrate              # applica all'ultimo stato
make migrate-down         # rollback ultima migration
make migrate-history      # cronologia
make migration MSG="..."  # genera nuova migration vuota
```

Per resettare completamente il DB locale (perdita dati):

```bash
make infra-reset
make dev
make migrate
```

## Test

```bash
make test                 # tutto
make test-cov             # con report coverage HTML
cd backend && uv run pytest tests/test_rls.py -v   # solo un file
```

Convenzione: i test che toccano il DB chiedono la fixture `seed_auth_user` o `system_session`. I test puramente unit (no DB) usano solo `client` e `auth_headers`.

## Stato corrente (M1 — completato)

- [x] Pydantic Settings con tipi forti + SecretStr
- [x] Structlog con context propagation (request_id)
- [x] SQLAlchemy 2.0 async + asyncpg + connection pool
- [x] Alembic + prima migration (schema auth + profiles + RLS + trigger)
- [x] JWT validation (HMAC HS256, audience, expiry, algorithm pinning)
- [x] FastAPI app factory + lifespan + RequestIdMiddleware
- [x] Exception handlers per AuthError → HTTP status
- [x] Endpoint `/health`, `/users/me`, `/profiles/me` (GET + PATCH)
- [x] Repository pattern + service layer + just-in-time provisioning
- [x] Test integration con DB reale + verifica RLS esplicita

Prossima milestone: **M2 — Content Ingestion** (presigned URLs verso Backblaze B2, upload diretto, validazione MIME).

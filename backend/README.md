# EchoMind -- Backend

Servizio Python (FastAPI + Celery) per estrazione e gestione del knowledge graph.

> Decisioni architetturali tracciate in [`/docs/adr/`](../docs/adr/).

## Requisiti host

- Python >= 3.12 (vedi [`/.python-version`](../.python-version))
- [`uv`](https://docs.astral.sh/uv/) >= 0.4
- Docker Desktop con Compose v2 (per Postgres + RabbitMQ + Redis locali)
- `libmagic` a livello di sistema (MIME detection M2): macOS `brew install libmagic`, Ubuntu `apt install libmagic1`
- `ffmpeg` a livello di sistema (chunking audio M4): macOS `brew install ffmpeg`, Ubuntu `apt install ffmpeg`

## Quick start (sviluppo)

Tutti i comandi vanno lanciati dalla **root del repo** tramite `make`:

```bash
# Setup primo avvio
make install            # crea .venv backend, installa runtime + dev deps
make precommit-install  # registra hook locali pre-commit
cp ../.env.example ../.env
# (poi popola .env con i secret veri -- vedi sezione sotto)

# Avvio quotidiano
make dev                # avvia Postgres + RabbitMQ + Redis locali
make migrate            # applica le migration Alembic
make serve              # uvicorn con hot-reload su :8000
make worker             # (altro terminale) worker Celery su coda echomind.default

# Loop di sviluppo
make format             # auto-fix ruff
make verify             # lint + typecheck + test (= ciò che CI verifica)
```

Endpoint disponibili:

**Identity (M1)**
- `GET   /api/v1/health` (no auth) -- liveness check
- `GET   /api/v1/users/me` -- claim del JWT corrente
- `GET   /api/v1/profiles/me` -- profile utente (lazy create)
- `PATCH /api/v1/profiles/me` -- aggiornamento parziale del profile

**Content Ingestion (M2)**
- `POST   /api/v1/documents` -- init upload (genera presigned URL B2)
- `POST   /api/v1/documents/{id}/confirm` -- conferma upload + MIME validation server-side
- `GET    /api/v1/documents` -- lista paginata (RLS-filtered)
- `GET    /api/v1/documents/{id}` -- dettaglio
- `DELETE /api/v1/documents/{id}` -- hard delete (B2 object + DB)

**Async jobs (M3)**
- `POST /api/v1/tasks/echo` -- accoda un task echo (202 Accepted, ritorna task_id)
- `GET  /api/v1/tasks` -- lista paginata dei propri task (RLS-filtered)
- `GET  /api/v1/tasks/{id}` -- stato/dettaglio di un task

**Media Processing (M4)**
- `POST /api/v1/documents/{id}/confirm` -- oltre a validare il MIME, accoda automaticamente la trascrizione del documento
- `GET  /api/v1/documents/{id}/transcript` -- testo estratto/trascritto (404 finche' non pronto; RLS-filtered)

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
| `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT` | Obbligatorie in produzione. In dev: opzionali (gli endpoint `/documents` ritornano 503 finché non configurate). Vedi [ADR-0004](../docs/adr/0004-content-ingestion.md) |
| `MAX_UPLOAD_SIZE_BYTES` | Default 50 MB |
| `UPLOAD_PRESIGN_TTL_SECONDS` | Default 900 (15 min). Cap a 3600 (1h) |
| `RABBITMQ_URL` | Broker Celery (AMQP). Default dev `amqp://guest:guest@localhost:5672//`. Vedi [ADR-0005](../docs/adr/0005-async-job-infrastructure.md) |
| `REDIS_URL` | Result backend Celery. Default dev `redis://localhost:6379/0` |
| `TASK_MAX_RETRIES` | Tentativi prima dello stato terminale `failed` (poi dead-letter). Default 3 |
| `TASK_RETRY_BACKOFF_SECONDS` | Base del backoff esponenziale tra i retry. Default 2 |
| `TASK_SOFT_TIME_LIMIT_SECONDS` | Soft time limit per task. Default 300 |
| `OPENAI_API_KEY`, `OPENAI_ORG_ID` | Whisper (trascrizione audio M4). Opzionali: solo i task su audio le richiedono, i documenti no. Vedi [ADR-0006](../docs/adr/0006-media-processing.md) |
| `WHISPER_MODEL` | Modello di trascrizione OpenAI. Default `whisper-1` |
| `WHISPER_MAX_CHUNK_BYTES` | Soglia di chunking audio, sotto il limite 25 MB di Whisper. Default 24 MB |
| `TRANSCRIPTION_SOFT_TIME_LIMIT_SECONDS` | Soft time limit del task di trascrizione. Default 1800 (30 min) |

Le altre (`SUPABASE_URL`, `NEO4J_*`, `ANTHROPIC_API_KEY`, ...) entrano in gioco nelle milestone successive.

### HS256 (dev/test locale)

Generare un secret random:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### ES256 (Supabase reale)

Dalla dashboard Supabase --> **JWT Keys --> Current Key --> Public Key**, copia il blocco JSON (JWK) e mettilo su singola riga in `.env`:

```env
SUPABASE_JWT_ALGORITHM=ES256
SUPABASE_JWT_PUBLIC_KEY={"keys":[{"kty":"EC","crv":"P-256","alg":"ES256","x":"...","y":"...","key_ops":["verify"]}]}
```

## Architettura layered

```
HTTP request
  |  FastAPI router (api/v1/*.py)
  |  Depends --> middleware --> exception handlers
  |  Service layer (services/*.py)        <- business logic
  |  Repository (db/repositories/*.py)    <- query SQL
  |  AsyncSession con RLS bound (db/session.py)
  v  PostgreSQL (con RLS enforcement)
```

Pattern di sicurezza: **doppio ruolo Postgres** (`echomind` superuser per migration, `app_runtime` non-superuser per query app). Vedi [`ADR-0002`](../docs/adr/0002-m1-auth-and-persistence.md).

## Worker asincrono (M3)

L'API e il worker sono **due processi separati** che condividono lo stesso codice (model, repository) ma hanno entrypoint ed engine DB distinti:

```
API (uvicorn)                      RabbitMQ                    worker (celery)
  POST /tasks/echo                  exchange/queue              consuma il messaggio
    INSERT tasks(queued, RLS)  -->  echomind.default     -->   run_echo:
    enqueue (task_id = row id)                                   running --> succeeded
  202 {task_id, queued}                                          oppure  --> failed
                                    echomind.dead (DLQ)  <--   retry esauriti: Reject
  GET /tasks/{id} (RLS) <-- legge lo stato dalla tabella tasks (verità di dominio)
```

- **Broker**: RabbitMQ (`RABBITMQ_URL`). **Result backend interno Celery**: Redis (`REDIS_URL`).
- **Verità di dominio** sullo stato: tabella Postgres `tasks` (RLS owner-based), non il result backend Redis -- così l'API la espone filtrata per-utente. Vedi [ADR-0005](../docs/adr/0005-async-job-infrastructure.md).
- **Dead-letter queue**: la coda di lavoro è dichiarata con `x-dead-letter-exchange`; un task che esaurisce i retry diventa `failed` e il messaggio viene instradato nella coda `echomind.dead`, ispezionabile dalla management UI di RabbitMQ (`http://localhost:15672`, guest/guest).

```bash
make worker   # avvia il worker (richiede `make dev` per RabbitMQ + Redis)
```

> Troubleshooting: se cambi gli `queue_arguments` (es. la config DLX) e RabbitMQ risponde `PRECONDITION_FAILED (406)`, la coda esiste già con argomenti diversi. Elimina la coda vecchia dalla management UI (o con `make infra-reset`) e riavvia il worker.

## Media processing (M4)

Il primo worker reale, agganciato al motore di M3. Dopo il confirm di un upload, l'API accoda un task `transcribe`; il worker scarica il file da B2, lo trasforma in testo e salva un `transcript`.

```
API (confirm)                       worker (celery)                     DB
  POST /documents/{id}/confirm        run_transcribe:                   transcripts
    valida MIME --> uploaded            scarica il file da B2            (1:1 col documento,
    accoda transcribe (RLS)            estrae (PDF/DOCX/TXT) o            RLS SELECT-only)
                                       trascrive (audio --> Whisper)
                                       normalizza --> upsert transcript
  GET /documents/{id}/transcript <-- legge il testo (404 finche' non pronto)
```

- **Pipeline pura** (`processing/`): parser PDF/DOCX/TXT, normalizzazione, chunking audio, client Whisper. Sincrona e testabile in isolamento; il `Transcriber` e' un Protocol iniettato (i test usano un fake, niente rete). Vedi [ADR-0006](../docs/adr/0006-media-processing.md).
- **Errori retryable vs permanenti**: file corrotto / non supportato / vuoto / 404 storage --> `failed` subito (niente retry); blip di rete / 5xx di Whisper --> retry con backoff. Riusa la dead-letter di M3.
- **Chunking audio**: file sotto 24 MB inviati as-is; oltre, divisi per tempo e ri-esportati in MP3 (sotto il limite di 25 MB di Whisper). Richiede **ffmpeg** (vedi Requisiti host).
- **Trigger automatico**: la trascrizione parte da `confirm_upload`, sulla sola transizione `pending --> uploaded`, nella stessa transazione della request (enqueue fallito --> rollback, il confirm risponde 503).
- **Trascrizione audio reale**: richiede `OPENAI_API_KEY`; i documenti testuali no.

## Layout

```
backend/
|-- pyproject.toml                   # metadata + tooling config (PEP 621/735)
|-- uv.lock                          # lock file deterministico
|-- alembic.ini                      # config Alembic
|-- alembic/
|   |-- env.py                       # runtime migration (async)
|   `-- versions/                    # singole migration versionate
|-- src/echomind/                    # src-layout
|   |-- main.py                      # FastAPI app factory + lifespan
|   |-- core/                        # config, logging, security (JWT)
|   |-- db/
|   |   |-- base.py                  # DeclarativeBase + naming convention
|   |   |-- session.py               # async engine + sessionmaker + RLS
|   |   |-- models/                  # SQLAlchemy ORM models
|   |   `-- repositories/            # query CRUD
|   |-- services/                    # business logic (API-agnostic)
|   |-- schemas/                     # Pydantic I/O schemas
|   |-- worker/                      # Celery app + runtime + task (M3/M4)
|   |   |-- celery_app.py            # Celery app: broker, backend, code + DLX
|   |   |-- runtime.py               # engine NullPool + run_async + factory storage/transcriber
|   |   `-- tasks/                   # echo.py (M3) + transcribe.py (M4: worker reale)
|   |-- processing/                  # pipeline media M4 (pura, sincrona)
|   |   |-- documents.py             # parser PDF/DOCX/TXT
|   |   |-- audio.py                 # chunking audio (pydub/ffmpeg)
|   |   |-- transcription.py         # Transcriber Protocol + impl OpenAI/Whisper
|   |   |-- normalize.py             # normalizzazione testo
|   |   |-- pipeline.py              # process_media (orchestratore)
|   |   `-- errors.py                # errori di dominio con flag retryable
|   `-- api/
|       |-- deps.py                  # FastAPI dependencies
|       `-- v1/                      # endpoint versione 1
`-- tests/
    |-- conftest.py                  # fixture: app, client, jwt, db, enqueue stub
    |-- test_config.py               # Pydantic Settings
    |-- test_security.py             # JWT validation
    |-- test_models.py               # SQLAlchemy schema dichiarato
    |-- test_task_model.py           # schema tabella tasks
    |-- test_task_service.py         # TaskService (repo mock + enqueue patchato)
    |-- test_worker_echo.py          # core async run_echo (DB reale)
    |-- test_tasks_api.py            # endpoint /tasks end-to-end
    |-- test_processing.py           # pipeline media pura (parser, normalize, Whisper mock)
    |-- test_transcript_model.py     # schema tabella transcripts
    |-- test_worker_transcribe.py    # core async run_transcribe (DB reale)
    |-- test_transcript_api.py       # endpoint transcript end-to-end
    `-- test_rls.py                  # isolamento RLS (profiles, documents, tasks, transcripts)
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

Convenzione: i test che toccano il DB chiedono la fixture `seed_auth_user` o `system_session`. I test del worker chiamano `run_echo` direttamente e usano `captured_enqueues` per stubbare l'enqueue Celery (niente broker reale nei test; la pipeline reale è coperta dallo smoke test locale).

## Stato corrente (M4 -- completato)

### M1 -- Identity & Persistence Foundations
- [x] Pydantic Settings con tipi forti + SecretStr + validator cross-field
- [x] Structlog con context propagation (request_id)
- [x] SQLAlchemy 2.0 async + asyncpg + connection pool
- [x] Alembic con prima migration (schema auth + profiles + RLS + trigger)
- [x] JWT validation HS256/ES256 + audience + expiry + algorithm pinning
- [x] FastAPI app factory + lifespan + RequestIdMiddleware
- [x] Exception handlers per errori di dominio --> HTTP status
- [x] Endpoint `/health`, `/users/me`, `/profiles/me`
- [x] Repository pattern + service layer + just-in-time provisioning
- [x] Test integration con DB reale + verifica RLS esplicita

### M2 -- Content Ingestion
- [x] `B2StorageService` wrapper boto3 con S3-compatible API
- [x] Alembic migration 0002 (documents + RLS + indice composito + ENUM)
- [x] Schema documents con FK CASCADE a profiles, lifecycle pending --> uploaded/failed
- [x] Presigned URL PUT verso B2 con `Content-Length` constraint (mitigazione "size lying")
- [x] MIME validation server-side via `python-magic` (magic bytes)
- [x] `MIME_EQUIVALENCES` map per gestire alias noti (DOCX-as-ZIP, WAV, M4A-as-MP4)
- [x] Endpoint `/documents` (POST init, POST confirm, GET list, GET detail, DELETE)
- [x] Hard delete idempotente (B2 object + DB row in ordine)
- [x] Just-in-time profile provisioning come dependency (riusabile per future risorse owned)
- [x] Test integration con moto (mock S3) + RLS isolation cross-utente
- [x] Graceful degradation: 503 quando B2 non configurato in dev

### M3 -- Async Job Infrastructure
- [x] Celery app con broker RabbitMQ + result backend Redis (`worker/celery_app.py`)
- [x] Code con dead-letter exchange/queue reale (`echomind.default` --> `echomind.dead`)
- [x] Alembic migration 0003 (tasks + RLS SELECT/INSERT + indice composito + ENUM status)
- [x] Tabella `tasks` come verità di dominio dello stato (RLS), non il result backend Redis
- [x] Echo task con retry + backoff esponenziale + jitter, stato terminale `failed`, dead-letter
- [x] Ponte sync<->async nel worker (engine NullPool + `asyncio.run`, fork-safe)
- [x] Idempotenza del task (re-delivery at-least-once = no-op su riga terminale)
- [x] Endpoint `/tasks` (POST echo 202, GET list, GET detail) + isolamento RLS
- [x] Test: schema, service (mock), core worker (DB reale), API end-to-end, RLS

### M4 -- Media Processing Pipeline
- [x] Pacchetto `processing/` puro e sincrono (parser PDF/DOCX/TXT, normalizzazione, chunking audio, client Whisper)
- [x] `Transcriber` come Protocol iniettato (testabile con fake, provider sostituibile)
- [x] Tassonomia errori `retryable` (permanente --> failed subito; transiente --> retry con backoff)
- [x] Chunking audio sotto il limite di 25 MB di Whisper (fast-path + split per tempo in MP3)
- [x] Alembic migration 0004 (transcripts 1:1 con documents + RLS SELECT-only + indice composito)
- [x] Worker reale `transcribe` agganciato al motore M3 (core async + wrapper Celery, DI di storage/transcriber)
- [x] Trigger automatico della trascrizione sul confirm dell'upload (stessa transazione, rollback-safe)
- [x] Endpoint `GET /documents/{id}/transcript` + isolamento RLS dei transcript
- [x] Test: pipeline pura (input golden + Whisper mock), core worker (DB reale), API, RLS

Prossima milestone: **M5 -- Knowledge Graph Extraction** (LLM extraction dai transcript, persistenza su Neo4j).

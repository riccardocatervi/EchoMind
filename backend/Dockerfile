# =============================================================================
# EchoMind — Immagine di produzione del backend (API FastAPI + worker Celery).
#
# Una SOLA immagine serve sia l'API sia il worker: condividono lo stesso codice
# (model, repository, config) e differiscono solo per il comando di avvio, che
# scegliamo nel compose. Questo e' il pattern descritto in backend/README.
#
# Build multi-stage:
#   - stage `builder`: installa le dipendenze con uv in un virtualenv isolato.
#     Sfrutta la cache di Docker: se pyproject/uv.lock non cambiano, lo strato
#     delle dipendenze (lento) non viene ricostruito.
#   - stage `runtime`: immagine finale snella. Copia solo il venv + il codice,
#     piu' le dipendenze DI SISTEMA che le librerie Python richiedono a runtime.
#
# Riproducibilita': `uv sync --frozen` rifiuta di muoversi dal lockfile, quindi
# l'immagine usa ESATTAMENTE le versioni di uv.lock (le stesse dei test/CI).
# =============================================================================

# --- Versione di uv pinnata (riproducibilita'): copiamo il binario statico
#     dall'immagine ufficiale, evitando un `pip install uv` nel layer. ----------
FROM ghcr.io/astral-sh/uv:0.5 AS uv

# -----------------------------------------------------------------------------
# STAGE 1 — builder: risolve e installa le dipendenze nel venv /app/.venv
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# UV_COMPILE_BYTECODE: precompila i .pyc → avvio piu' rapido del container.
# UV_LINK_MODE=copy: copia i file invece di hardlink (evita warning con la
#   cache montata su filesystem diverso).
# UV_PYTHON_DOWNLOADS=never: usa il Python di sistema dell'immagine, non scaricarne.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

# 1) Installa SOLO le dipendenze (senza il progetto), usando il lockfile.
#    Layer separato e cache-friendly: cambia solo se pyproject/uv.lock cambiano.
#    --no-dev: esclude il dependency-group `dev` (ruff/mypy/pytest), inutile in prod.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 2) Copia il codice e installa il progetto stesso (src-layout, hatchling).
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# STAGE 2 — runtime: immagine finale eseguibile
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Dipendenze DI SISTEMA richieste a runtime dalle librerie Python:
#   - ffmpeg:   richiesto da pydub per il chunking audio (limite 25MB di Whisper)
#   - libmagic1: richiesto da python-magic per la MIME detection lato server
# (vedi commenti in backend/pyproject.toml). Senza queste, l'import funziona ma
# le funzionalita' falliscono a runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Best practice di sicurezza: non girare come root dentro il container.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copia il venv + il codice gia' pronti dal builder. Il venv usa path assoluti
# /app/.venv: coerenti perche' WORKDIR e' /app in entrambi gli stage.
COPY --from=builder --chown=app:app /app /app

USER app

EXPOSE 8000

# Comando di DEFAULT = API. Il worker sovrascrive questo `command` nel compose.
# `--factory`: echomind.main:create_app e' una factory function, non un'app gia'
# istanziata. Niente `--reload` in produzione (e' solo per lo sviluppo).
#
# `--workers 1`: un solo processo uvicorn. Due ragioni:
#   1. RAM: sul t3.micro (1 GB) un processo in meno lascia respiro a worker
#      Celery + RabbitMQ + Redis.
#   2. Evita la corsa all'avvio in cui due processi creano in parallelo i
#      vincoli/indici Neo4j → deadlock su AuraDB (graph_store_unavailable).
# Per il carico di una demo a utente singolo, un worker e' abbondante.
CMD ["uvicorn", "echomind.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

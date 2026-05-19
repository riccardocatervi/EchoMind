"""FastAPI app factory + lifespan + middleware.

Pattern "create_app(settings)":
    - L'app NON è creata all'import time
    - Test e produzione possono passare Settings diverse
    - Lifespan gestisce startup/shutdown idempotente

Risorse globali condivise (engine, sessionmaker, settings) vivono in
`app.state`. Accesso negli endpoint via `request.app.state.engine`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from echomind import __version__
from echomind.api.v1.router import router as api_v1_router
from echomind.core.config import Settings, get_settings
from echomind.core.logging import configure_logging, get_logger, request_id_var
from echomind.db.session import create_engine, create_session_maker


# -----------------------------------------------------------------------------
# Middleware: request_id
# -----------------------------------------------------------------------------
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Genera un UUID per ogni richiesta e lo propaga nei log.

    Pattern:
    1. Se il client manda `X-Request-ID`, lo riusa (utile per trace distribuiti).
       Altrimenti, ne genera uno nuovo.
    2. Setta `request_id_var` (ContextVar di logging.py) → tutti i log emessi
       durante questa richiesta includono il request_id.
    3. Aggiunge `X-Request-ID` alla response → il client può loggare lo stesso ID.

    Async-safe: ContextVar è isolato per task asyncio.
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[self.HEADER_NAME] = request_id
        return response


# -----------------------------------------------------------------------------
# Lifespan: startup / shutdown
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inizializza risorse all'avvio, le dismette allo spegnimento.

    Tutto ciò che vive un'intera "sessione" dell'app (engine DB, http client,
    cache, ...) viene creato qui e salvato in `app.state`.
    """
    settings: Settings = app.state.settings

    # Logging: configurato qui per essere coerente con env (json in prod).
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.app_env != "development",
    )
    log = get_logger("echomind.lifespan")
    log.info("app_starting", env=settings.app_env, version=__version__)

    # Engine SQLAlchemy: connection pool aperto, condiviso tra tutte le request.
    app.state.engine = create_engine(settings)
    app.state.session_maker = create_session_maker(app.state.engine)
    log.info("db_engine_ready")

    yield  # ← qui gira l'app

    # Shutdown
    log.info("app_shutting_down")
    await app.state.engine.dispose()
    log.info("db_engine_disposed")


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------
def create_app(settings: Settings | None = None) -> FastAPI:
    """Costruisce e ritorna l'app FastAPI.

    Args:
        settings: opzionale. Default → `get_settings()` (singleton da .env).
            I test possono passare Settings custom per override.

    Returns:
        FastAPI configurata, pronta a essere passata a uvicorn o TestClient.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="EchoMind",
        version=__version__,
        description="AI-Powered GraphRAG: documenti/audio → knowledge graph interattivi.",
        lifespan=lifespan,
        # Documentazione interattiva: Swagger UI su /docs, ReDoc su /redoc.
        # In produzione, valutare se disabilitarli (settings.app_env).
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    # Settings disponibili in app.state — accessibili dagli endpoint via request.
    app.state.settings = settings

    # Middleware: ordine = ordine di esecuzione "in entrata".
    app.add_middleware(RequestIdMiddleware)

    # Router applicativo (v1)
    app.include_router(api_v1_router)

    return app


# -----------------------------------------------------------------------------
# Istanza modulo-level (per uvicorn)
# -----------------------------------------------------------------------------
# Comando: `uvicorn echomind.main:app --reload`
# I test usano `create_app(test_settings)` invece di questa istanza globale.
app = create_app()

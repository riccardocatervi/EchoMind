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
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from echomind import __version__
from echomind.api.v1.router import router as api_v1_router
from echomind.core.config import Settings, get_settings
from echomind.core.logging import configure_logging, get_logger, request_id_var
from echomind.core.security import (
    ExpiredTokenError,
    InvalidAudienceError,
    InvalidTokenError,
    MissingClaimError,
    MissingTokenError,
)
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

    # Exception handlers: mappa eccezioni di dominio a HTTP status.
    _register_exception_handlers(app)

    # Router applicativo (v1)
    app.include_router(api_v1_router)

    return app


# -----------------------------------------------------------------------------
# Exception handlers: errori di auth → HTTP status appropriati
# -----------------------------------------------------------------------------
def _register_exception_handlers(app: FastAPI) -> None:
    """Mappa le eccezioni di dominio a risposte HTTP coerenti.

    Senza handler globale, queste eccezioni causerebbero 500 generici.
    Definendo qui la mappatura, ogni endpoint protetto riceve gratis
    il comportamento corretto.

    Convenzione (RFC 7235 + best practice):
        401 Unauthorized:  identità non verificabile (token mancante/invalido/scaduto)
        403 Forbidden:     identità verificata ma claim insufficienti
    """

    def _make_response(status: int, code: str, detail: str) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse(
            status_code=status,
            content={"detail": detail, "code": code},
            headers=headers,
        )

    @app.exception_handler(MissingTokenError)
    async def _on_missing_token(request: Request, exc: MissingTokenError) -> JSONResponse:
        return _make_response(401, "missing_token", str(exc))

    @app.exception_handler(ExpiredTokenError)
    async def _on_expired_token(request: Request, exc: ExpiredTokenError) -> JSONResponse:
        return _make_response(401, "expired_token", "Token has expired")

    @app.exception_handler(InvalidTokenError)
    async def _on_invalid_token(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return _make_response(401, "invalid_token", "Invalid authentication token")

    @app.exception_handler(InvalidAudienceError)
    async def _on_invalid_audience(request: Request, exc: InvalidAudienceError) -> JSONResponse:
        return _make_response(401, "invalid_audience", "Token audience mismatch")

    @app.exception_handler(MissingClaimError)
    async def _on_missing_claim(request: Request, exc: MissingClaimError) -> JSONResponse:
        # 403: il token è valido e firmato, ma manca un claim obbligatorio
        # → non è una questione di identità (401) ma di autorizzazione (403).
        return _make_response(403, "missing_claim", "Required JWT claim is missing")


# -----------------------------------------------------------------------------
# Lazy entry point per uvicorn
# -----------------------------------------------------------------------------
# Comando di avvio: `uvicorn echomind.main:create_app --factory`
# (vedi target `serve` nel Makefile).
#
# Niente `app = create_app()` a module-level: l'esecuzione qui richiede
# che TUTTE le env var siano già caricate, ma in CI/test non lo sono.
# Con --factory uvicorn chiama create_app() solo all'avvio del server,
# non al solo import del modulo.
#
# I test usano direttamente `create_app(test_settings)` via la fixture `app`
# in `tests/conftest.py`.

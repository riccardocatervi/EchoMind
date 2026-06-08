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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from echomind import __version__
from echomind.api.v1.router import router as api_v1_router
from echomind.core.config import Settings, get_settings, require_secret
from echomind.core.logging import configure_logging, get_logger, request_id_var
from echomind.core.security import (
    ExpiredTokenError,
    InvalidAudienceError,
    InvalidTokenError,
    MissingClaimError,
    MissingTokenError,
)
from echomind.db.session import create_engine, create_session_maker
from echomind.extraction.errors import EmbeddingError, LLMError
from echomind.services import (
    B2StorageService,
    DocumentAlreadyConfirmedError,
    DocumentNotFoundError,
    ExtractionNotReadyError,
    GraphNotReadyError,
    GraphStoreError,
    RagNotReadyError,
    RagUnavailableError,
    StorageError,
    SummaryNotFoundError,
    TaskEnqueueError,
    TaskNotFoundError,
    TranscriptNotFoundError,
)
from echomind.services.graph_store import Neo4jGraphStore


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

    # Storage service (B2 / S3-compatible). Opzionale in dev: se le settings
    # B2 non sono popolate, restiamo a None e gli endpoint /documents
    # ritornano 503 (Service Unavailable). In produzione le settings sono
    # obbligatorie (validator cross-field) → from_settings non fallisce.
    try:
        app.state.storage = B2StorageService.from_settings(settings)
        log.info("storage_service_ready")
    except StorageError as exc:
        app.state.storage = None
        log.warning("storage_service_unavailable", reason=str(exc))

    # Graph store (Neo4j, M5). Opzionale in dev come lo storage: se NEO4J_* non
    # sono popolate, restiamo a None e GET /documents/{id}/graph ritorna 503.
    # ensure_constraints crea il vincolo di unicita' (idempotente). Best-effort:
    # se Neo4j non e' raggiungibile/configurato, restiamo a None senza bloccare
    # l'avvio (l'API resta su; il worker scrive comunque il proprio graph store).
    try:
        graph_store = Neo4jGraphStore.from_settings(settings)
        await graph_store.ensure_constraints()
        app.state.graph_store = graph_store
        log.info("graph_store_ready")
    except Exception as exc:
        # Startup resiliente: Neo4j assente/giu' non deve impedire l'avvio dell'API.
        app.state.graph_store = None
        log.warning("graph_store_unavailable", reason=str(exc))

    # RAG components (embedder + answerer lato API, M8). Opzionali come gli altri
    # backend: se GEMINI_API_KEY manca o Gemini non risponde, restiamo a None e
    # POST /documents/{id}/ask ritorna 503 (RagUnavailableError dal dep).
    # Riuso del client Gemini gia' creato dal worker (stesso pattern: sincrono,
    # thread-safe): qui lo creiamo per l'API, separato da quello del worker.
    try:
        from google import genai as _genai

        from echomind.extraction.gemini import GeminiEmbedder
        from echomind.rag.gemini import GeminiRagAnswerer

        _api_key = require_secret(
            settings.gemini_api_key,
            env_name="GEMINI_API_KEY",
            hint="Richiesta per il Q&A RAG (POST /documents/{id}/ask).",
        )
        _client = _genai.Client(api_key=_api_key)
        app.state.rag_embedder = GeminiEmbedder(
            client=_client,
            model=settings.gemini_embedding_model,
            dimensions=settings.embedding_dimensions,
            max_retries=settings.gemini_max_retries,
        )
        app.state.rag_answerer = GeminiRagAnswerer(
            client=_client,
            model=settings.gemini_model,
            thinking_budget=settings.gemini_thinking_budget,
            max_retries=settings.gemini_max_retries,
        )
        log.info("rag_components_ready")
    except Exception as exc:
        app.state.rag_embedder = None
        app.state.rag_answerer = None
        log.warning("rag_components_unavailable", reason=str(exc))

    yield  # ← qui gira l'app

    # Shutdown
    log.info("app_shutting_down")
    if app.state.graph_store is not None:
        await app.state.graph_store.close()
        log.info("graph_store_closed")
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

    # Middleware. NB (Starlette): l'ULTIMO middleware aggiunto e' il piu' ESTERNO,
    # cioe' gira per PRIMO sulla richiesta in entrata e per ULTIMO sulla risposta.
    # Vogliamo CORS piu' esterno di RequestId, cosi':
    #   - intercetta il preflight OPTIONS prima del routing;
    #   - aggiunge gli header CORS anche alle risposte d'errore (401/404/503/...).
    # Percio' RequestId va aggiunto PRIMA, CORS DOPO.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

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

    # -------------------------------------------------------------------------
    # Errori di dominio Document (M2)
    # -------------------------------------------------------------------------
    @app.exception_handler(DocumentNotFoundError)
    async def _on_document_not_found(request: Request, exc: DocumentNotFoundError) -> JSONResponse:
        # 404 anche se il documento esiste ma appartiene a un altro utente:
        # RLS lo nasconde alla SELECT → repository ritorna None → DocumentNotFoundError.
        # Indistinguibilità by design: non rivela l'esistenza di documenti altrui.
        return _make_response(404, "document_not_found", "Document not found")

    @app.exception_handler(DocumentAlreadyConfirmedError)
    async def _on_document_already_confirmed(
        request: Request, exc: DocumentAlreadyConfirmedError
    ) -> JSONResponse:
        # 409 Conflict: stato corrente incompatibile con l'operazione.
        return _make_response(409, "document_already_confirmed", str(exc))

    @app.exception_handler(StorageError)
    async def _on_storage_error(request: Request, exc: StorageError) -> JSONResponse:
        # 503: dipendenza esterna (B2) non disponibile o malconfigurata.
        # Il client può riprovare; non è colpa sua.
        return _make_response(503, "storage_unavailable", "Storage backend error")

    # -------------------------------------------------------------------------
    # Errori di dominio Task (M3)
    # -------------------------------------------------------------------------
    @app.exception_handler(TaskNotFoundError)
    async def _on_task_not_found(request: Request, exc: TaskNotFoundError) -> JSONResponse:
        # 404 anche se il task esiste ma e' di un altro utente (RLS lo nasconde
        # --> repository ritorna None). Indistinguibilita' by design.
        return _make_response(404, "task_not_found", "Task not found")

    @app.exception_handler(TaskEnqueueError)
    async def _on_task_enqueue_error(request: Request, exc: TaskEnqueueError) -> JSONResponse:
        # 503: il broker (RabbitMQ) non e' raggiungibile. Il client puo' riprovare.
        return _make_response(503, "task_enqueue_failed", "Task queue backend error")

    # -------------------------------------------------------------------------
    # Errori di dominio Transcript (M4)
    # -------------------------------------------------------------------------
    @app.exception_handler(TranscriptNotFoundError)
    async def _on_transcript_not_found(
        request: Request, exc: TranscriptNotFoundError
    ) -> JSONResponse:
        # 404 anche se il transcript non e' ancora pronto (in elaborazione) o e'
        # di un altro utente (RLS lo nasconde). Il client fa polling fino a 200.
        return _make_response(404, "transcript_not_found", "Transcript not found")

    # -------------------------------------------------------------------------
    # Errori di dominio KnowledgeExtraction (M5)
    # -------------------------------------------------------------------------
    @app.exception_handler(SummaryNotFoundError)
    async def _on_summary_not_found(request: Request, exc: SummaryNotFoundError) -> JSONResponse:
        # 404: riassunto non ancora pronto (in elaborazione/fallito) o non tuo (RLS).
        return _make_response(404, "summary_not_found", "Summary not found")

    @app.exception_handler(GraphNotReadyError)
    async def _on_graph_not_ready(request: Request, exc: GraphNotReadyError) -> JSONResponse:
        # 404: grafo non ancora estratto, vuoto, o documento non tuo. Indistinguibili.
        return _make_response(404, "graph_not_found", "Graph not found")

    @app.exception_handler(ExtractionNotReadyError)
    async def _on_extraction_not_ready(
        request: Request, exc: ExtractionNotReadyError
    ) -> JSONResponse:
        # 409 Conflict: il documento non e' in uno stato estraibile (manca il transcript).
        return _make_response(409, "extraction_not_ready", str(exc))

    @app.exception_handler(GraphStoreError)
    async def _on_graph_store_error(request: Request, exc: GraphStoreError) -> JSONResponse:
        # 503: il backend del grafo (Neo4j) non e' disponibile/configurato.
        return _make_response(503, "graph_unavailable", "Graph backend error")

    # -------------------------------------------------------------------------
    # Errori di dominio RAG (M8)
    # -------------------------------------------------------------------------
    @app.exception_handler(RagNotReadyError)
    async def _on_rag_not_ready(request: Request, exc: RagNotReadyError) -> JSONResponse:
        # 404: documento non trovato/non tuo (RLS), o elaborazione non completata.
        # Indistinguibili by design.
        return _make_response(404, "document_not_ready_for_qa", "Document not available for Q&A")

    @app.exception_handler(RagUnavailableError)
    async def _on_rag_unavailable(request: Request, exc: RagUnavailableError) -> JSONResponse:
        # 503: GEMINI_API_KEY assente o componenti RAG non inizializzati.
        return _make_response(503, "rag_unavailable", "RAG backend not configured")

    @app.exception_handler(LLMError)
    async def _on_llm_error(request: Request, exc: LLMError) -> JSONResponse:
        # 503 (transitorio: 429/timeout/5xx) o 422 (permanente: 4xx non-429).
        if exc.retryable:
            return _make_response(503, "llm_unavailable", "LLM backend temporarily unavailable")
        return _make_response(422, "llm_rejected", "Request rejected by LLM backend")

    @app.exception_handler(EmbeddingError)
    async def _on_embedding_error(request: Request, exc: EmbeddingError) -> JSONResponse:
        # Stesso schema di LLMError: transiente -> 503, permanente -> 422.
        if exc.retryable:
            return _make_response(
                503, "embedding_unavailable", "Embedding backend temporarily unavailable"
            )
        return _make_response(422, "embedding_rejected", "Request rejected by embedding backend")


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

"""Endpoint /users — informazioni sull'utente autenticato.

GET  /users/me   -- echo dei claim JWT (debug, verifica auth pipeline)
DELETE /users/me -- cancellazione completa dell'account e di tutti i dati

Ordine delle operazioni in DELETE:
  1. Raccoglie le storage_key di tutti i documenti dell'utente (prima di
     cancellare la riga in Postgres, che le renderebbe irraggiungibili).
  2. Cancella il sottografo Neo4j dell'utente (best-effort: non blocca se
     Neo4j non e' disponibile).
  3. Cancella auth.users → la CASCADE DB rimuove profile + documenti +
     tasks + transcripts + summaries + embeddings.
     - In produzione (con SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):
       chiama l'Admin REST API di Supabase.
     - In sviluppo locale (Docker, auth.users nel Postgres locale):
       usa una sessione di sistema non-RLS.
  4. Cancella i file da B2 (best-effort: se fallisce, l'utente e' comunque
     eliminato dal DB; gli oggetti orfani possono essere ripuliti da un job).
"""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.api.deps import ClaimsDep, SessionMakerDep, SettingsDep, UserIdDep
from echomind.core.config import Settings
from echomind.core.logging import get_logger
from echomind.core.security import JWTClaims
from echomind.db.models import Document
from echomind.services.graph_store import GraphStore
from echomind.services.storage import B2StorageService

router = APIRouter(prefix="/users", tags=["users"])
log = get_logger(__name__)


# -----------------------------------------------------------------------------
# GET /users/me
# -----------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=JWTClaims,
    summary="Claim del token JWT corrente",
    description=(
        "Ritorna i claim del JWT autenticato (sub, aud, exp, eventuali extra). "
        "Niente accesso DB: utile per debug e per il client per sapere 'chi sono'."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        403: {"description": "Token valido ma claim obbligatori mancanti"},
    },
)
async def get_me(claims: ClaimsDep) -> JWTClaims:
    """Ritorna i claim del JWT corrente, gia' validati."""
    return claims


# -----------------------------------------------------------------------------
# DELETE /users/me
# -----------------------------------------------------------------------------
@router.delete(
    "/me",
    status_code=204,
    summary="Cancella l'account utente",
    description=(
        "Rimuove l'account e tutti i dati associati: documenti, trascrizioni, "
        "riassunti, grafi di conoscenza e file nel bucket B2. "
        "L'operazione e' irreversibile."
    ),
    responses={
        204: {"description": "Account eliminato con successo"},
        401: {"description": "Token mancante, invalido o scaduto"},
    },
)
async def delete_me(
    user_id: UserIdDep,
    settings: SettingsDep,
    session_maker: SessionMakerDep,
    request: Request,
) -> None:
    """Cancella l'account e tutti i dati dell'utente autenticato."""
    graph_store: GraphStore | None = request.app.state.graph_store
    storage: B2StorageService | None = request.app.state.storage

    # ------------------------------------------------------------------
    # 1. Raccolta preventiva delle storage_key (prima della CASCADE DB)
    # ------------------------------------------------------------------
    storage_keys: list[str] = []
    async with session_maker() as system_session, system_session.begin():
        result = await system_session.execute(
            select(Document.storage_key).where(Document.owner_id == user_id)
        )
        storage_keys = list(result.scalars().all())
    log.info("user_delete_started", user_id=str(user_id), files=len(storage_keys))

    # ------------------------------------------------------------------
    # 2. Neo4j: rimozione sottografo dell'utente (best-effort)
    # ------------------------------------------------------------------
    if graph_store is not None:
        try:
            await graph_store.delete_owner_graph(owner_id=user_id)
            log.info("user_graph_deleted", user_id=str(user_id))
        except Exception as exc:
            # Non blocca: Neo4j offline o nodi assenti sono casi accettabili.
            log.warning("user_graph_delete_failed", user_id=str(user_id), error=str(exc))

    # ------------------------------------------------------------------
    # 3. Cancellazione auth.users → CASCADE su profiles + tutto il resto
    # ------------------------------------------------------------------
    await _delete_auth_user(user_id, settings=settings, session_maker=session_maker)
    log.info("user_auth_deleted", user_id=str(user_id))

    # ------------------------------------------------------------------
    # 4. B2: rimozione file (best-effort, post-CASCADE)
    # ------------------------------------------------------------------
    if storage is not None:
        for key in storage_keys:
            try:
                await storage.delete_object(key)
            except Exception as exc:
                # Oggetti orfani accettabili: un job di cleanup li raccogliera'.
                log.warning("user_file_delete_failed", key=key, error=str(exc))

    log.info("user_delete_complete", user_id=str(user_id))


# -----------------------------------------------------------------------------
# Helper: cancellazione utente da Supabase (produzione vs sviluppo)
# -----------------------------------------------------------------------------
async def _delete_auth_user(
    user_id: UUID,
    *,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Cancella l'utente da auth.users.

    - Con SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY: chiama l'Admin REST API.
      La CASCADE on auth.users rimuove il profile e tutti i dati associati.
    - Senza credenziali (sviluppo locale, Docker):
      usa una sessione di sistema non-RLS per DELETE SQL diretto.
      In dev l'auth.users e' nel Postgres locale e il DELETE e' permesso.
    """
    if settings.supabase_url and settings.supabase_service_role_key:
        service_role = settings.supabase_service_role_key.get_secret_value()
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                url,
                headers={
                    "Authorization": f"Bearer {service_role}",
                    "apikey": service_role,
                },
            )
            response.raise_for_status()
        return

    # Fallback sviluppo: DELETE diretto su auth.users (Docker Postgres locale)
    async with session_maker() as system_session, system_session.begin():
        await system_session.execute(
            text("DELETE FROM auth.users WHERE id = :id"),
            {"id": str(user_id)},
        )
    log.info("user_auth_deleted_via_sql", user_id=str(user_id))

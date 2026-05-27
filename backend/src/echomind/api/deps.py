"""FastAPI dependencies per autenticazione e DB session.

Catena di dipendenze (frecce = "dipende da"):

    get_settings_dep  ←  app.state.settings
        ↑
    get_authorization_header  ←  header HTTP "Authorization"
        ↑
    get_current_claims  ←  valida JWT, ritorna JWTClaims tipizzati
        ↑
    get_current_user_id  ←  estrae UUID dal claim "sub"
        ↑
    get_db_session  ←  apre AsyncSession + bind RLS (SET LOCAL ROLE + claim)

Ogni livello è una funzione async pura: testabile in isolamento,
overridabile con `app.dependency_overrides[...]` nei test.

Tipo `Annotated[T, Depends(...)]`: forma moderna (Python 3.9+) che
separa tipo statico (T) dai metadati FastAPI (Depends). Preferita
al vecchio `param: T = Depends(...)` per chiarezza e mypy support.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from echomind.core.config import Settings
from echomind.core.security import JWTClaims, decode_and_validate, extract_bearer_token
from echomind.db.repositories import ProfileRepository
from echomind.db.session import set_rls_user
from echomind.services import ProfileService


# -----------------------------------------------------------------------------
# Risorse globali (lifespan-bound, vive in app.state)
# -----------------------------------------------------------------------------
def get_settings_dep(request: Request) -> Settings:
    """Ritorna le Settings registrate in app.state dal lifespan."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_engine_dep(request: Request) -> AsyncEngine:
    """Ritorna l'engine SQLAlchemy creato nel lifespan."""
    return request.app.state.engine  # type: ignore[no-any-return]


def get_session_maker_dep(request: Request) -> async_sessionmaker[AsyncSession]:
    """Ritorna il sessionmaker creato nel lifespan."""
    return request.app.state.session_maker  # type: ignore[no-any-return]


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionMakerDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_maker_dep)]


# -----------------------------------------------------------------------------
# Estrazione header + validazione JWT
# -----------------------------------------------------------------------------
async def get_current_claims(
    settings: SettingsDep,
    authorization: Annotated[
        str | None,
        Header(
            alias="Authorization",
            description="Bearer <jwt>. Richiesto per gli endpoint protetti.",
        ),
    ] = None,
) -> JWTClaims:
    """Estrae header, decoda e valida JWT, ritorna i claim tipizzati.

    Solleva eccezioni `AuthError` (mappate ad HTTP status da main.py).
    Nessun try/except qui: le eccezioni viaggiano fino al handler globale,
    che le converte in JSON envelope.
    """
    token = extract_bearer_token(authorization)
    return decode_and_validate(token, settings)


ClaimsDep = Annotated[JWTClaims, Depends(get_current_claims)]


async def get_current_user_id(claims: ClaimsDep) -> UUID:
    """Estrae solo l'UUID dell'utente dal JWT.

    Da preferire a `get_current_claims` quando all'endpoint serve solo l'ID
    (la maggior parte dei casi). Niente esposizione di claim extra non usati.
    """
    return claims.sub


UserIdDep = Annotated[UUID, Depends(get_current_user_id)]


# -----------------------------------------------------------------------------
# Database session (con RLS per utente autenticato)
# -----------------------------------------------------------------------------
async def get_db_session(
    user_id: UserIdDep,
    session_maker: SessionMakerDep,
) -> AsyncIterator[AsyncSession]:
    """Apre una AsyncSession con RLS attiva per l'utente corrente.

    Sequenza:
    1. Apre sessione (connessione presa dal pool)
    2. Apre transazione
    3. `SET LOCAL ROLE app_runtime` + setta claim JWT
    4. yield della sessione all'endpoint
    5. Alla fine: commit (se nessun errore) + close

    Le RLS policy filtreranno automaticamente le query.
    """
    async with session_maker() as session, session.begin():
        await set_rls_user(session, user_id)
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_db_session_unauthenticated(
    session_maker: SessionMakerDep,
) -> AsyncIterator[AsyncSession]:
    """Apre una sessione SENZA RLS (per endpoint pubblici o jobs di sistema).

    ATTENZIONE: niente filtri user_id. Usare SOLO quando:
    - l'endpoint non ha auth (es. /health)
    - è un task amministrativo (es. cleanup batch)
    """
    async with session_maker() as session:
        yield session


UnauthenticatedSessionDep = Annotated[AsyncSession, Depends(get_db_session_unauthenticated)]


# -----------------------------------------------------------------------------
# Service layer dependencies
# -----------------------------------------------------------------------------
async def get_profile_service(
    session: SessionDep,
    session_maker: SessionMakerDep,
) -> ProfileService:
    """Costruisce un ProfileService con la sessione RLS-bound dell'utente.

    Il `session_maker` aggiuntivo serve al service per aprire una seconda
    sessione "system" (non-RLS) durante il just-in-time provisioning.
    """
    return ProfileService(
        repository=ProfileRepository(session),
        system_session_maker=session_maker,
    )


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]

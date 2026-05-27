"""Fixtures globali di pytest.

Convenzione: questo file è auto-discovered da pytest. Tutte le fixture
qui definite sono utilizzabili senza import nei test.

Fixture principali:
- `test_settings`     → Settings deterministici per test
- `app`               → FastAPI app costruita con test_settings (lifespan simulato)
- `client`            → httpx.AsyncClient connesso all'app (no rete reale)
- `make_jwt`          → factory per generare JWT firmati con il secret di test
- `auth_headers`      → header Authorization con JWT valido per uno user_id
- `system_session`    → AsyncSession superuser (per seed e cleanup DB nei test)
- `seed_auth_user`    → factory per inserire un utente in auth.users
- `cleanup_db`        → autouse: truncate profiles + auth.users dopo ogni test
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import jwt as pyjwt
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.core.config import Settings
from echomind.db.session import create_engine, create_session_maker
from echomind.main import create_app

# Secret abbastanza lungo da non triggerare InsecureKeyLengthWarning di pyjwt
# (riusato in test_security.py per gli stessi motivi). Non è una credenziale
# reale: serve solo per firmare JWT dentro la test suite.
TEST_JWT_SECRET = (
    "test-secret-with-at-least-64-bytes-for-hs256-and-hs512-attack-tests"  # gitleaks:allow
)
TEST_AUDIENCE = "authenticated"


@pytest.fixture
def test_settings() -> Settings:
    """Settings deterministici per i test, senza dipendenza da .env."""
    return Settings.model_construct(
        app_env="development",
        log_level="WARNING",  # meno verboso nei test
        database_url="postgresql+asyncpg://echomind:echomind_dev@localhost:5432/echomind",
        supabase_jwt_secret=SecretStr(TEST_JWT_SECRET),
        supabase_jwt_algorithm="HS256",
        supabase_jwt_audience=TEST_AUDIENCE,
    )


@pytest_asyncio.fixture
async def app(test_settings: Settings) -> AsyncIterator[object]:
    """FastAPI app costruita con test_settings + engine/sessionmaker iniettati.

    `httpx.ASGITransport` NON triggera il lifespan, quindi simuliamo
    manualmente lo startup (creazione engine + session_maker) e lo shutdown
    (dispose engine) qui.

    Vantaggi rispetto a `asgi-lifespan.LifespanManager`:
    - niente dipendenza extra
    - controllo fine sui parametri (es. test che usano engine custom)
    """
    application = create_app(test_settings)
    application.state.engine = create_engine(test_settings)
    application.state.session_maker = create_session_maker(application.state.engine)
    try:
        yield application
    finally:
        await application.state.engine.dispose()


@pytest_asyncio.fixture
async def client(app: object) -> AsyncIterator[httpx.AsyncClient]:
    """httpx.AsyncClient che parla all'app in-process (no rete reale).

    Trasporto ASGI diretto: tutto vive nello stesso event loop, niente
    socket. Più veloce e deterministico di un TestClient HTTP reale.
    """
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------------
# Fixture per generare JWT firmati (per test endpoint protetti)
# -----------------------------------------------------------------------------
@pytest.fixture
def make_jwt() -> Callable[..., str]:
    """Factory: ritorna una funzione `make_jwt(sub=..., ...)` che firma un JWT.

    Esempio d'uso nei test:

        def test_something(make_jwt):
            token = make_jwt(sub=str(uuid4()))
            # ...

    I parametri di default producono un token valido con exp=+1h e
    audience="authenticated".
    """

    def _make(
        *,
        sub: str | None = None,
        aud: str = TEST_AUDIENCE,
        exp_offset_seconds: int = 3600,
        algorithm: str = "HS256",
        secret: str = TEST_JWT_SECRET,
        extra_claims: dict[str, object] | None = None,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "aud": aud,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=exp_offset_seconds)).timestamp()),
        }
        if sub is not None:
            payload["sub"] = sub
        if extra_claims:
            payload.update(extra_claims)
        return pyjwt.encode(payload, secret, algorithm=algorithm)

    return _make


@pytest.fixture
def auth_headers(make_jwt: Callable[..., str]) -> Callable[[UUID | None], dict[str, str]]:
    """Factory: header Authorization Bearer con JWT valido per uno user_id.

    Esempio:
        def test_something(auth_headers, client):
            user_id = uuid4()
            response = await client.get("/api/v1/users/me", headers=auth_headers(user_id))
    """

    def _make(user_id: UUID | None = None) -> dict[str, str]:
        sub = str(user_id or uuid4())
        token = make_jwt(sub=sub)
        return {"Authorization": f"Bearer {token}"}

    return _make


# -----------------------------------------------------------------------------
# Database integration fixtures
# -----------------------------------------------------------------------------
@pytest_asyncio.fixture
async def system_session(app: object) -> AsyncIterator[AsyncSession]:
    """Sessione AsyncSession come ruolo `echomind` (superuser, bypassa RLS).

    Usata per seed/cleanup nei test integration. NON simula un utente:
    è il "service_role" equivalente Supabase.
    """
    session_maker = app.state.session_maker  # type: ignore[attr-defined]
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def seed_auth_user(
    system_session: AsyncSession,
) -> AsyncIterator[Callable[[UUID], Awaitable[None]]]:
    """Factory che inserisce un utente fittizio in `auth.users`.

    Pattern: `await seed_auth_user(user_id)` → riga creata.
    Necessaria prima di creare profile, perché FK `profiles.id → auth.users.id`.

    Cleanup automatico: alla fine del test, TRUNCATE CASCADE su `auth.users`
    rimuove anche tutti i profile creati (via FK ON DELETE CASCADE).
    Questo garantisce isolamento tra test senza richiedere autouse globale.
    """

    async def _insert(user_id: UUID) -> None:
        await system_session.execute(
            text("INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": str(user_id)},
        )
        await system_session.commit()

    yield _insert

    # Cleanup post-test: rimuove tutto ciò creato durante il test
    await system_session.execute(text("TRUNCATE TABLE auth.users CASCADE"))
    await system_session.commit()

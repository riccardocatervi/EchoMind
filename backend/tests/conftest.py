"""Fixtures globali di pytest.

Convenzione: questo file è auto-discovered da pytest. Tutte le fixture
qui definite sono utilizzabili senza import nei test.

Fixture principali:
- `test_settings`  → Settings deterministici per test
- `app`            → FastAPI app costruita con test_settings
- `client`         → httpx.AsyncClient connesso all'app (no rete reale)
- `make_jwt`       → factory per generare JWT firmati con il secret di test
- `auth_headers`   → header Authorization con JWT valido per uno user_id
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import jwt as pyjwt
import pytest
import pytest_asyncio
from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.main import create_app

# Secret abbastanza lungo da non triggerare InsecureKeyLengthWarning di pyjwt
# (riusato in test_security.py per gli stessi motivi)
TEST_JWT_SECRET = "test-secret-with-at-least-64-bytes-for-hs256-and-hs512-attack-tests"
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
    """FastAPI app costruita con test_settings.

    Usa il lifespan tramite LifespanManager → engine+sessionmaker vengono
    creati come in produzione. Per evitare di toccare il DB reale durante
    i test che non lo richiedono, vedi i test che mockano `app.state.engine`.

    Nota: yieldiamo l'app come `object` per ergonomia di import; il tipo
    reale è `FastAPI` ma evitiamo l'import a livello globale.
    """
    application = create_app(test_settings)
    # LifespanManager garantisce che startup/shutdown vengano eseguiti
    # anche con httpx.AsyncClient (che non li triggera nativamente).
    # In step futuri useremo `asgi_lifespan.LifespanManager` per controllo
    # più fine; per ora il test di /health è banale e non richiede lifespan
    # completo. Restituiamo l'app "raw".
    yield application


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

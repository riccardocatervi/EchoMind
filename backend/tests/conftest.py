"""Fixtures globali di pytest.

Convenzione: questo file è auto-discovered da pytest. Tutte le fixture
qui definite sono utilizzabili senza import nei test.

Fixture principali (espanderemo in step successivi):
- `test_settings`  → Settings deterministici per test
- `app`            → FastAPI app costruita con test_settings
- `client`         → httpx.AsyncClient connesso all'app (no rete reale)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.main import create_app

# Secret abbastanza lungo da non triggerare InsecureKeyLengthWarning di pyjwt
# (riusato in test_security.py per gli stessi motivi)
TEST_JWT_SECRET = "test-secret-with-at-least-64-bytes-for-hs256-and-hs512-attack-tests"


@pytest.fixture
def test_settings() -> Settings:
    """Settings deterministici per i test, senza dipendenza da .env."""
    return Settings.model_construct(
        app_env="development",
        log_level="WARNING",  # meno verboso nei test
        database_url="postgresql+asyncpg://echomind:echomind_dev@localhost:5432/echomind",
        supabase_jwt_secret=SecretStr(TEST_JWT_SECRET),
        supabase_jwt_algorithm="HS256",
        supabase_jwt_audience="authenticated",
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

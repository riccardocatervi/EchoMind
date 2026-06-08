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
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt as pyjwt
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.core.config import Settings
from echomind.db.session import create_engine, create_session_maker
from echomind.main import create_app
from echomind.services.storage import B2StorageService

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
    # Storage default a None: i test che lo richiedono attivano la fixture
    # `s3_mock_storage` che lo sostituisce con un client moto.
    application.state.storage = None
    # Graph store default a None (M5): i test del grafo lo sostituiscono con un
    # FakeGraphStore via dependency_overrides. None --> GET /graph ritorna 503.
    application.state.graph_store = None
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

    Pattern: `await seed_auth_user(user_id)` --> riga creata.
    Necessaria prima di creare profile, perche' FK `profiles.id -> auth.users.id`.

    Cleanup automatico: alla fine del test vengono rimossi SOLO gli utenti
    inseriti da questo fixture (DELETE WHERE id = ANY(...)).
    La DELETE a cascata (FK ON DELETE CASCADE) rimuove profile, documenti e
    tutto il resto creato da quel test -- senza toccare utenti pre-esistenti.

    ATTENZIONE -- vecchio approccio (TRUNCATE CASCADE):
      Il TRUNCATE azzerava l'intera tabella auth.users, cancellando anche gli
      utenti "reali" presenti nel DB di sviluppo. Il DELETE selettivo qui sotto
      risolve il problema: ogni test pulisce solo i propri dati.
    """
    inserted_ids: list[UUID] = []

    async def _insert(user_id: UUID) -> None:
        await system_session.execute(
            text("INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": str(user_id)},
        )
        await system_session.commit()
        inserted_ids.append(user_id)

    yield _insert

    # Cleanup post-test: rimuove SOLO gli utenti creati da questo test.
    # La FK ON DELETE CASCADE si occupa di profile, documents, tasks, ecc.
    if inserted_ids:
        await system_session.execute(
            text("DELETE FROM auth.users WHERE id = ANY(:ids)"),
            {"ids": [str(uid) for uid in inserted_ids]},
        )
        await system_session.commit()


# -----------------------------------------------------------------------------
# Storage (moto mock S3) — per i test integration di /documents
# -----------------------------------------------------------------------------
TEST_BUCKET = "echomind-test"


@pytest_asyncio.fixture
async def s3_mock_storage(app: object) -> AsyncIterator[B2StorageService]:
    """Sostituisce `app.state.storage` con un B2StorageService puntato a moto.

    Pattern: il lifespan reale tenta `from_settings(...)` e fallisce (B2 vuote
    nei test_settings). Il valore di app.state.storage diventa None. Qui lo
    rimpiazziamo con un'istanza valida ma puntata a S3 in-memory.

    Yieldiamo il service per test che vogliono ispezionare direttamente il
    bucket (es. verifica che un object sia stato uploadato/cancellato).
    """
    import boto3
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=TEST_BUCKET)
        storage = B2StorageService(
            client=client,
            bucket=TEST_BUCKET,
            presign_ttl_seconds=900,
        )
        original = getattr(app.state, "storage", None)  # type: ignore[attr-defined]
        app.state.storage = storage  # type: ignore[attr-defined]
        try:
            yield storage
        finally:
            app.state.storage = original  # type: ignore[attr-defined]


# -----------------------------------------------------------------------------
# Async jobs (M3): stub dell'enqueue Celery + sessionmaker per i test del worker
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def captured_enqueues(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Patcha l'enqueue Celery di TUTTI i task: nessun test tocca il broker reale.

    autouse=True: l'invariante "niente broker nei test" vale per ogni test, anche
    per quelli che accodano in modo INDIRETTO -- es. il confirm di un documento
    (M4) triggera la trascrizione. I test che vogliono ispezionare gli enqueue
    ricevono comunque la lista richiedendo `captured_enqueues` per nome.

    Cattura gli argomenti di ogni enqueue (per le assert). La pipeline reale
    (worker che consuma da RabbitMQ) e' verificata nello smoke test locale,
    non qui -- eager mode confliggerebbe con l'event loop di pytest-asyncio.
    """
    from echomind.worker.tasks.echo import echo_task
    from echomind.worker.tasks.extract import extract_task
    from echomind.worker.tasks.transcribe import transcribe_task

    calls: list[dict[str, Any]] = []

    def _fake_apply_async(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(echo_task, "apply_async", _fake_apply_async)
    monkeypatch.setattr(transcribe_task, "apply_async", _fake_apply_async)
    # extract viene accodato anche INDIRETTAMENTE dal seam di transcribe (M5):
    # patchiamo anche il suo apply_async cosi' nessun test pubblica sul broker.
    monkeypatch.setattr(extract_task, "apply_async", _fake_apply_async)
    return calls


@pytest.fixture
def db_session_maker(app: object) -> async_sessionmaker[AsyncSession]:
    """Sessionmaker dell'app: usato per invocare `run_echo` direttamente nei
    test del worker, nello stesso event loop del test (niente Celery/asyncio.run).
    """
    return app.state.session_maker  # type: ignore[attr-defined,no-any-return]

"""Test del core async dell'echo task (`run_echo`) con DB reale.

Chiamiamo `run_echo` DIRETTAMENTE (niente Celery, niente asyncio.run): gira
nello stesso event loop del test, quindi nessun conflitto di loop. La riga
'queued' di partenza la creiamo via POST /tasks/echo (enqueue patchato), cosi'
riusiamo il path reale di provisioning profile + INSERT sotto RLS.

Copre: queued->running->succeeded, fallimento non terminale (resta running),
fallimento terminale (failed + error), idempotenza su riga terminale, riga
assente (no-op).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.worker.tasks.echo import run_echo

ECHO_ENDPOINT = "/api/v1/tasks/echo"


async def _enqueue(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    message: str = "hi",
    fail: bool = False,
) -> str:
    """Crea una riga task (status=queued) via API. Ritorna il task_id."""
    response = await client.post(
        ECHO_ENDPOINT, headers=headers, json={"message": message, "fail": fail}
    )
    assert response.status_code == 202, response.text
    return str(response.json()["task_id"])


async def _row(system_session: AsyncSession, task_id: str) -> Any:
    """Stato della riga task letto come superuser (bypassa RLS)."""
    result = await system_session.execute(
        text(
            "SELECT status::text AS status, error, retries, "
            "result->>'echo' AS echo, "
            "(started_at IS NOT NULL) AS has_started, "
            "(finished_at IS NOT NULL) AS has_finished "
            "FROM public.tasks WHERE id = :id"
        ),
        {"id": task_id},
    )
    return result.mappings().one()


@pytest.mark.asyncio
async def test_success_marks_succeeded(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    captured_enqueues: list[dict[str, Any]],
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    task_id = await _enqueue(client, auth_headers(user_id), message="ciao")

    outcome = await run_echo(
        task_id=UUID(task_id),
        message="ciao",
        fail=False,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
    )

    assert outcome.kind == "succeeded"
    assert outcome.result == {"echo": "ciao", "length": 4, "attempt": 1}

    row = await _row(system_session, task_id)
    assert row["status"] == "succeeded"
    assert row["echo"] == "ciao"
    assert row["error"] is None
    assert row["has_started"] is True
    assert row["has_finished"] is True


@pytest.mark.asyncio
async def test_fail_non_terminal_stays_running(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    captured_enqueues: list[dict[str, Any]],
) -> None:
    """fail=True ma non ultimo tentativo: outcome 'retry', riga resta 'running'."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    task_id = await _enqueue(client, auth_headers(user_id), message="boom", fail=True)

    outcome = await run_echo(
        task_id=UUID(task_id),
        message="boom",
        fail=True,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
    )

    assert outcome.kind == "retry"
    row = await _row(system_session, task_id)
    assert row["status"] == "running"  # non ancora terminale
    assert row["error"] is None  # l'errore si salva solo a terminale
    assert row["has_started"] is True
    assert row["has_finished"] is False


@pytest.mark.asyncio
async def test_fail_terminal_marks_failed(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    captured_enqueues: list[dict[str, Any]],
) -> None:
    """fail=True all'ultimo tentativo: outcome 'failed_terminal', riga 'failed'."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    task_id = await _enqueue(client, auth_headers(user_id), message="boom", fail=True)

    outcome = await run_echo(
        task_id=UUID(task_id),
        message="boom",
        fail=True,
        attempt=2,
        is_last_attempt=True,
        session_maker=db_session_maker,
    )

    assert outcome.kind == "failed_terminal"
    row = await _row(system_session, task_id)
    assert row["status"] == "failed"
    assert row["error"] is not None
    assert row["retries"] == 2
    assert row["has_finished"] is True


@pytest.mark.asyncio
async def test_idempotent_on_terminal_row(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    captured_enqueues: list[dict[str, Any]],
) -> None:
    """Re-delivery (at-least-once) su riga gia' terminale: no-op idempotente."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    task_id = await _enqueue(client, auth_headers(user_id), message="x")

    # Prima esecuzione: succeeded
    await run_echo(
        task_id=UUID(task_id),
        message="x",
        fail=False,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
    )
    # Seconda esecuzione (riconsegna): deve essere no-op
    outcome = await run_echo(
        task_id=UUID(task_id),
        message="x",
        fail=True,  # anche se ora chiedesse fail, NON deve toccare la riga
        attempt=1,
        is_last_attempt=True,
        session_maker=db_session_maker,
    )

    assert outcome.kind == "already_done"
    row = await _row(system_session, task_id)
    assert row["status"] == "succeeded"  # invariato
    assert row["error"] is None


@pytest.mark.asyncio
async def test_missing_row_is_noop(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Un task_id senza riga (es. INSERT rollbackato): no-op, nessun crash."""
    outcome = await run_echo(
        task_id=uuid4(),
        message="ghost",
        fail=False,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
    )
    assert outcome.kind == "already_done"

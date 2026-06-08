"""Test integration end-to-end di /api/v1/tasks.

Pipeline coperta: HTTP --> JWT --> RLS bind --> endpoint --> service --> repository --> DB
                                                       (enqueue Celery patchato)

I test NON eseguono il worker: dopo l'enqueue la riga resta 'queued'.
L'esecuzione reale (running -> succeeded/failed) e' nei test del worker
(test_worker_echo) e nello smoke test locale.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

ENDPOINT = "/api/v1/tasks"
ECHO = "/api/v1/tasks/echo"


# =============================================================================
# POST /tasks/echo
# =============================================================================
class TestEnqueue:
    @pytest.mark.asyncio
    async def test_returns_202_and_creates_queued_row(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        response = await client.post(ECHO, headers=headers, json={"message": "ciao"})
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "queued"
        task_id = body["task_id"]

        # La riga esiste ed e' ancora 'queued' (il worker non gira nei test)
        detail = await client.get(f"{ENDPOINT}/{task_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["status"] == "queued"
        assert detail.json()["task_type"] == "echo"
        assert detail.json()["payload"] == {"message": "ciao", "fail": False}

        # L'enqueue e' stato invocato una volta col task_id corretto
        assert len(captured_enqueues) == 1
        assert captured_enqueues[0]["kwargs"]["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: httpx.AsyncClient) -> None:
        response = await client.post(ECHO, json={"message": "x"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_empty_message(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.post(ECHO, headers=auth_headers(user_id), json={"message": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_extra_field(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        """extra='forbid': un campo non previsto -> 422."""
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.post(
            ECHO,
            headers=auth_headers(user_id),
            json={"message": "x", "bogus": 1},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_503_and_rollback_when_broker_down(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Broker giu': 503 e nessuna riga orfana (rollback della request)."""
        from echomind.worker.tasks.echo import echo_task

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(echo_task, "apply_async", _boom)

        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        response = await client.post(ECHO, headers=headers, json={"message": "x"})
        assert response.status_code == 503
        assert response.json()["code"] == "task_enqueue_failed"

        # Rollback: nessun task creato
        listing = await client.get(ENDPOINT, headers=headers)
        assert listing.json() == []


# =============================================================================
# GET /tasks
# =============================================================================
class TestList:
    @pytest.mark.asyncio
    async def test_empty_for_new_user(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.get(ENDPOINT, headers=auth_headers(user_id))
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_lists_own_sorted_desc(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        for i in range(3):
            await client.post(ECHO, headers=headers, json={"message": f"m{i}"})

        response = await client.get(ENDPOINT, headers=headers)
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 3
        for t in tasks:
            assert t["status"] == "queued"
        assert tasks[0]["created_at"] >= tasks[1]["created_at"] >= tasks[2]["created_at"]

    @pytest.mark.asyncio
    async def test_pagination(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        for i in range(5):
            await client.post(ECHO, headers=headers, json={"message": f"m{i}"})

        page1 = await client.get(f"{ENDPOINT}?limit=2&offset=0", headers=headers)
        page2 = await client.get(f"{ENDPOINT}?limit=2&offset=2", headers=headers)
        assert len(page1.json()) == 2
        assert len(page2.json()) == 2
        ids = {t["id"] for t in page1.json()} | {t["id"] for t in page2.json()}
        assert len(ids) == 4

    @pytest.mark.asyncio
    async def test_rejects_invalid_limit(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.get(f"{ENDPOINT}?limit=101", headers=auth_headers(user_id))
        assert response.status_code == 422


# =============================================================================
# GET /tasks/{id}
# =============================================================================
class TestGet:
    @pytest.mark.asyncio
    async def test_returns_own_task(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        enq = await client.post(ECHO, headers=headers, json={"message": "x"})
        task_id = enq.json()["task_id"]

        response = await client.get(f"{ENDPOINT}/{task_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == task_id

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.get(f"{ENDPOINT}/{uuid4()}", headers=auth_headers(user_id))
        assert response.status_code == 404
        assert response.json()["code"] == "task_not_found"

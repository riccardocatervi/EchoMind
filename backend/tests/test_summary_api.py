"""Test integration di GET /api/v1/documents/{id}/summary.

Pipeline: HTTP --> JWT --> RLS bind --> endpoint --> SummaryService --> repository --> DB.
Il summary viene seedato come superuser (system_session); l'utente lo legge via API,
filtrato da RLS (summary_select_own).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _seed_summary(
    session: AsyncSession,
    *,
    owner_id: UUID,
    overview: str = "panoramica del documento",
) -> UUID:
    """Crea profile + document + summary per `owner_id`. Ritorna il document_id."""
    await session.execute(
        text(
            "INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u') ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(owner_id)},
    )
    doc_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.documents (id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_id), "owner": str(owner_id), "key": f"users/{owner_id}/{doc_id}"},
    )
    await session.execute(
        text(
            "INSERT INTO public.summaries (id, document_id, owner_id, overview, sections, meta) "
            "VALUES (:id, :doc, :owner, :ov, CAST(:sec AS jsonb), CAST(:meta AS jsonb))"
        ),
        {
            "id": str(uuid4()),
            "doc": str(doc_id),
            "owner": str(owner_id),
            "ov": overview,
            "sec": json.dumps([{"title": "Tema 1", "content": "dettaglio 1"}]),
            "meta": json.dumps({"node_count": 12, "relationship_count": 18}),
        },
    )
    await session.commit()
    return doc_id


async def test_returns_summary(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_summary(system_session, owner_id=user_id)

    response = await client.get(
        f"/api/v1/documents/{doc_id}/summary", headers=auth_headers(user_id)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == str(doc_id)
    assert body["owner_id"] == str(user_id)
    assert body["overview"] == "panoramica del documento"
    assert body["sections"] == [{"title": "Tema 1", "content": "dettaglio 1"}]
    assert body["meta"]["node_count"] == 12


async def test_404_when_no_summary(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    response = await client.get(
        f"/api/v1/documents/{uuid4()}/summary", headers=auth_headers(user_id)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "summary_not_found"


async def test_404_for_other_users_summary(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """RLS: il summary di Bob e' invisibile ad Alice (404, non rivela l'esistenza)."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)
    bob_doc_id = await _seed_summary(system_session, owner_id=bob_id)

    response = await client.get(
        f"/api/v1/documents/{bob_doc_id}/summary", headers=auth_headers(alice_id)
    )
    assert response.status_code == 404


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid4()}/summary")
    assert response.status_code == 401

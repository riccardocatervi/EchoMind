"""Test integration di POST /api/v1/documents/{id}/extract (trigger manuale).

Verifica: 202 + enqueue del task 'extract' quando il transcript e' pronto; 409 se
manca il transcript; 404 per documento inesistente/altrui (RLS); 401 senza auth.
L'enqueue Celery e' patchato (captured_enqueues, autouse): niente broker reale.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.services.storage import B2StorageService

pytestmark = pytest.mark.asyncio


async def _seed_profile_and_document(session: AsyncSession, owner_id: UUID) -> UUID:
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
    return doc_id


async def _seed_doc_with_transcript(session: AsyncSession, owner_id: UUID) -> UUID:
    doc_id = await _seed_profile_and_document(session, owner_id)
    await session.execute(
        text(
            "INSERT INTO public.transcripts (id, document_id, owner_id, source_type, content, char_count) "
            "VALUES (:id, :doc, :owner, 'document', 'testo', 5)"
        ),
        {"id": str(uuid4()), "doc": str(doc_id), "owner": str(owner_id)},
    )
    await session.commit()
    return doc_id


async def _seed_doc_only(session: AsyncSession, owner_id: UUID) -> UUID:
    doc_id = await _seed_profile_and_document(session, owner_id)
    await session.commit()
    return doc_id


async def test_enqueues_extract_when_transcript_ready(
    client: httpx.AsyncClient,
    s3_mock_storage: B2StorageService,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
    captured_enqueues: list[dict[str, Any]],
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_doc_with_transcript(system_session, user_id)

    response = await client.post(
        f"/api/v1/documents/{doc_id}/extract", headers=auth_headers(user_id)
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert "task_id" in body
    assert body["status"] == "queued"
    # L'enqueue di extract e' stato catturato (args = [task_id]).
    assert any(call["kwargs"].get("args") == [body["task_id"]] for call in captured_enqueues)


async def test_409_without_transcript(
    client: httpx.AsyncClient,
    s3_mock_storage: B2StorageService,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_doc_only(system_session, user_id)

    response = await client.post(
        f"/api/v1/documents/{doc_id}/extract", headers=auth_headers(user_id)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "extraction_not_ready"


async def test_404_for_other_users_document(
    client: httpx.AsyncClient,
    s3_mock_storage: B2StorageService,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    alice_id, bob_id = uuid4(), uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)
    bob_doc_id = await _seed_doc_with_transcript(system_session, bob_id)

    response = await client.post(
        f"/api/v1/documents/{bob_doc_id}/extract", headers=auth_headers(alice_id)
    )
    assert response.status_code == 404


async def test_404_for_nonexistent_document(
    client: httpx.AsyncClient,
    s3_mock_storage: B2StorageService,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    response = await client.post(
        f"/api/v1/documents/{uuid4()}/extract", headers=auth_headers(user_id)
    )
    assert response.status_code == 404


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/v1/documents/{uuid4()}/extract")
    assert response.status_code == 401

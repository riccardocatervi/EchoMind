"""Test integration di GET /api/v1/documents/{id}/transcript.

Pipeline: HTTP --> JWT --> RLS bind --> endpoint --> TranscriptService --> repository --> DB.
Il transcript viene seedato come superuser (system_session); l'utente lo legge
via API, filtrato da RLS (transcript_select_own).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _seed_transcript(
    session: AsyncSession,
    *,
    owner_id: UUID,
    content: str = "testo trascritto",
    source_type: str = "document",
    language: str | None = None,
) -> UUID:
    """Crea profile + document + transcript per `owner_id`. Ritorna il document_id."""
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
            "INSERT INTO public.transcripts "
            "(id, document_id, owner_id, source_type, content, language, char_count) "
            "VALUES (:id, :doc, :owner, :st, :content, :lang, :cc)"
        ),
        {
            "id": str(uuid4()),
            "doc": str(doc_id),
            "owner": str(owner_id),
            "st": source_type,
            "content": content,
            "lang": language,
            "cc": len(content),
        },
    )
    await session.commit()
    return doc_id


async def test_returns_transcript(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_transcript(
        system_session,
        owner_id=user_id,
        content="ciao mondo",
        source_type="audio",
        language="italian",
    )

    response = await client.get(
        f"/api/v1/documents/{doc_id}/transcript", headers=auth_headers(user_id)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == str(doc_id)
    assert body["owner_id"] == str(user_id)
    assert body["content"] == "ciao mondo"
    assert body["source_type"] == "audio"
    assert body["language"] == "italian"
    assert body["char_count"] == len("ciao mondo")


async def test_404_when_no_transcript(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    response = await client.get(
        f"/api/v1/documents/{uuid4()}/transcript", headers=auth_headers(user_id)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "transcript_not_found"


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid4()}/transcript")
    assert response.status_code == 401

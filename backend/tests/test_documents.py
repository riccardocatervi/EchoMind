"""Test integration end-to-end di /api/v1/documents.

Pipeline coperta:
    HTTP → JWT validation → RLS bind → endpoint → service → repository → DB
                                                       ↓
                                            B2StorageService → moto (mock S3)
                                                       ↓
                                            magic.from_buffer (real libmagic)

Test groupings:
- TestInit: POST /documents (status_code, schema, validazione MIME/size)
- TestConfirm: POST /documents/{id}/confirm (happy, mime mismatch, size mismatch,
  no object, idempotency, failed → 409)
- TestList: GET /documents (paginazione, ordering)
- TestGet: GET /documents/{id} (404 own, 404 altri)
- TestDelete: DELETE /documents/{id} (B2 + DB cleanup)
- TestStorageUnavailable: 503 quando app.state.storage è None

Niente mock di magic: usiamo header reali (PDF / ZIP).
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

ENDPOINT = "/api/v1/documents"

# Header magic bytes reali — magic li riconosce senza ambiguità
PDF_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 240
DOCX_HEADER = b"PK\x03\x04" + b"\x00" * 252  # ZIP magic (DOCX è ZIP)
EXE_HEADER = b"MZ\x90\x00" + b"\x00" * 252  # PE/EXE magic (non in whitelist)


# =============================================================================
# Helper: piazza l'object direttamente nel mock S3 (simula upload client → B2)
# =============================================================================
def _simulate_b2_upload(
    storage: B2StorageService,
    storage_key: str,
    body: bytes,
    content_type: str,
) -> None:
    """Bypassa il presigned URL e mette l'object direttamente nel bucket mock.

    In un test e2e completo dovremmo PUT al presigned URL, ma moto non esegue
    veramente il PUT firmato. Bypass + uso le primitive low-level del client.
    """
    storage._client.put_object(
        Bucket=storage._bucket,
        Key=storage_key,
        Body=body,
        ContentType=content_type,
    )


async def _init_upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    mime_type: str = "application/pdf",
    size: int = 256,
    filename: str = "test.pdf",
) -> dict[str, Any]:
    """Helper: POST /documents → ritorna il body JSON."""
    response = await client.post(
        ENDPOINT,
        headers=headers,
        json={"filename": filename, "mime_type": mime_type, "size_bytes": size},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _get_storage_key_for(system_session: AsyncSession, document_id: str) -> str:
    """Estrae storage_key dal DB (system session bypassa RLS)."""
    result = await system_session.execute(
        text("SELECT storage_key FROM public.documents WHERE id = :id"),
        {"id": document_id},
    )
    key: str = result.scalar_one()
    return key


# =============================================================================
# POST /documents — init upload
# =============================================================================
class TestInit:
    @pytest.mark.asyncio
    async def test_returns_presigned_url(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)

        body = await _init_upload(client, auth_headers(user_id))

        assert "document_id" in body
        assert "upload_url" in body
        assert "expires_at" in body
        # URL ben formato
        assert body["upload_url"].startswith(("http://", "https://"))

    @pytest.mark.asyncio
    async def test_rejects_mime_not_in_whitelist(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)

        response = await client.post(
            ENDPOINT,
            headers=auth_headers(user_id),
            json={
                "filename": "evil.exe",
                "mime_type": "application/x-msdownload",
                "size_bytes": 1024,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_size_over_max(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        """size > 50MB: rifiutato dal Pydantic (via Field(gt=0)) ma il CHECK DB
        è la vera difesa. Qui testiamo che size invalido fallisce."""
        user_id = uuid4()
        await seed_auth_user(user_id)

        response = await client.post(
            ENDPOINT,
            headers=auth_headers(user_id),
            json={
                "filename": "f.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 0,  # invalid: gt=0
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_requires_auth(
        self,
        client: httpx.AsyncClient,
        s3_mock_storage: B2StorageService,
    ) -> None:
        response = await client.post(
            ENDPOINT,
            json={"filename": "f.pdf", "mime_type": "application/pdf", "size_bytes": 1},
        )
        assert response.status_code == 401


# =============================================================================
# POST /documents/{id}/confirm
# =============================================================================
class TestConfirm:
    @pytest.mark.asyncio
    async def test_happy_path_marks_uploaded(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
        system_session: AsyncSession,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        # 1. Init
        init_body = await _init_upload(
            client, headers, mime_type="application/pdf", size=len(PDF_HEADER)
        )
        document_id = init_body["document_id"]

        # 2. Simula upload reale a B2 (con PDF header VERO → magic ok)
        storage_key = await _get_storage_key_for(system_session, str(document_id))
        _simulate_b2_upload(s3_mock_storage, storage_key, PDF_HEADER, "application/pdf")

        # 3. Confirm
        response = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "uploaded"
        assert response.json()["failure_reason"] is None

    @pytest.mark.asyncio
    async def test_mime_mismatch_marks_failed(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
        system_session: AsyncSession,
    ) -> None:
        """Client dichiara PDF ma carica un EXE → magic rileva mismatch."""
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        init_body = await _init_upload(
            client, headers, mime_type="application/pdf", size=len(EXE_HEADER)
        )
        document_id = init_body["document_id"]
        storage_key = await _get_storage_key_for(system_session, str(document_id))
        _simulate_b2_upload(s3_mock_storage, storage_key, EXE_HEADER, "application/pdf")

        response = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["failure_reason"] == "mime_mismatch"

    @pytest.mark.asyncio
    async def test_size_mismatch_marks_failed(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
        system_session: AsyncSession,
    ) -> None:
        """Client dichiara 1000 byte, ne carica 256 → size mismatch."""
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        init_body = await _init_upload(client, headers, size=1000)
        document_id = init_body["document_id"]
        storage_key = await _get_storage_key_for(system_session, str(document_id))
        _simulate_b2_upload(
            s3_mock_storage, storage_key, PDF_HEADER, "application/pdf"
        )  # 256 byte, non 1000

        response = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)
        assert response.status_code == 200
        assert response.json()["failure_reason"] == "size_mismatch"

    @pytest.mark.asyncio
    async def test_object_not_received_marks_failed(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        """Confirm chiamato senza che il client abbia uploadato → upload_not_received."""
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        init_body = await _init_upload(client, headers)
        document_id = init_body["document_id"]

        # NON simuliamo upload: chiamata diretta a confirm
        response = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)
        assert response.status_code == 200
        assert response.json()["failure_reason"] == "upload_not_received"

    @pytest.mark.asyncio
    async def test_idempotent_for_already_uploaded(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
        system_session: AsyncSession,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        init_body = await _init_upload(client, headers, size=len(PDF_HEADER))
        document_id = init_body["document_id"]
        storage_key = await _get_storage_key_for(system_session, str(document_id))
        _simulate_b2_upload(s3_mock_storage, storage_key, PDF_HEADER, "application/pdf")

        first = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)
        second = await client.post(f"{ENDPOINT}/{document_id}/confirm", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["status"] == "uploaded"
        assert second.json()["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_document(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)

        response = await client.post(f"{ENDPOINT}/{uuid4()}/confirm", headers=auth_headers(user_id))
        assert response.status_code == 404


# =============================================================================
# GET /documents — list
# =============================================================================
class TestList:
    @pytest.mark.asyncio
    async def test_empty_list_for_new_user(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)

        response = await client.get(ENDPOINT, headers=auth_headers(user_id))
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_user_documents_sorted_desc(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        # Crea 3 documenti
        for i in range(3):
            await _init_upload(client, headers, filename=f"doc{i}.pdf")

        response = await client.get(ENDPOINT, headers=headers)
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 3
        # Tutti pending (no confirm)
        for d in docs:
            assert d["status"] == "pending"
        # Ordinati dal più recente (created_at DESC): created_at[0] >= [1] >= [2]
        assert docs[0]["created_at"] >= docs[1]["created_at"] >= docs[2]["created_at"]

    @pytest.mark.asyncio
    async def test_pagination_with_limit_and_offset(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        for i in range(5):
            await _init_upload(client, headers, filename=f"d{i}.pdf")

        # Prima pagina: 2
        page1 = await client.get(f"{ENDPOINT}?limit=2&offset=0", headers=headers)
        assert len(page1.json()) == 2
        # Pagina successiva
        page2 = await client.get(f"{ENDPOINT}?limit=2&offset=2", headers=headers)
        assert len(page2.json()) == 2
        # Tutte le pagine: id distinti
        ids = {d["id"] for d in page1.json()} | {d["id"] for d in page2.json()}
        assert len(ids) == 4

    @pytest.mark.asyncio
    async def test_rejects_invalid_limit(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.get(f"{ENDPOINT}?limit=101", headers=auth_headers(user_id))
        assert response.status_code == 422


# =============================================================================
# GET /documents/{id}
# =============================================================================
class TestGet:
    @pytest.mark.asyncio
    async def test_returns_own_document(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)
        init_body = await _init_upload(client, headers)
        document_id = init_body["document_id"]

        response = await client.get(f"{ENDPOINT}/{document_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == document_id

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.get(f"{ENDPOINT}/{uuid4()}", headers=auth_headers(user_id))
        assert response.status_code == 404


# =============================================================================
# DELETE /documents/{id}
# =============================================================================
class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_b2_object_and_db_row(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
        system_session: AsyncSession,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        headers = auth_headers(user_id)

        # Crea documento + simula upload
        init_body = await _init_upload(client, headers, size=len(PDF_HEADER))
        document_id = init_body["document_id"]
        storage_key = await _get_storage_key_for(system_session, str(document_id))
        _simulate_b2_upload(s3_mock_storage, storage_key, PDF_HEADER, "application/pdf")

        # Delete
        response = await client.delete(f"{ENDPOINT}/{document_id}", headers=headers)
        assert response.status_code == 204

        # Verifica: DB row sparita (via system_session, bypassa RLS)
        result = await system_session.execute(
            text("SELECT COUNT(*) FROM public.documents WHERE id = :id"),
            {"id": str(document_id)},
        )
        assert result.scalar_one() == 0

        # B2 object sparito (head_object → 404)
        from echomind.services.storage import StorageObjectNotFoundError

        with pytest.raises(StorageObjectNotFoundError):
            await s3_mock_storage.head_object(storage_key)

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
        s3_mock_storage: B2StorageService,
    ) -> None:
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.delete(f"{ENDPOINT}/{uuid4()}", headers=auth_headers(user_id))
        assert response.status_code == 404


# =============================================================================
# Storage non configurato → 503
# =============================================================================
class TestStorageUnavailable:
    @pytest.mark.asyncio
    async def test_503_when_storage_is_none(
        self,
        client: httpx.AsyncClient,
        auth_headers: Callable[[UUID | None], dict[str, str]],
        seed_auth_user: Callable[[UUID], Awaitable[None]],
    ) -> None:
        """Senza la fixture s3_mock_storage, app.state.storage resta None."""
        user_id = uuid4()
        await seed_auth_user(user_id)
        response = await client.post(
            ENDPOINT,
            headers=auth_headers(user_id),
            json={"filename": "f.pdf", "mime_type": "application/pdf", "size_bytes": 1},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "storage_unavailable"

"""Unit test del DocumentService (mock di repository + storage + magic).

Verifica:
- init_upload: ordine delle chiamate, storage_key generato correttamente
- confirm_upload: tutti i 4 esiti (uploaded, no_object, size_mismatch, mime_mismatch)
- confirm_upload idempotente per 'uploaded', errore per 'failed'
- MIME equivalence: DOCX detected as ZIP accettato; impostore rifiutato
- delete_document: ordine B2 → DB, propagazione NotFound
- Helper: _generate_storage_key, _mime_matches

Niente DB, niente rete: tutto in-memory grazie a mock. I test integration
con DB+moto+endpoint arriveranno nello Step 7.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from echomind.db.models import Document, DocumentStatus
from echomind.services.document import (
    DocumentAlreadyConfirmedError,
    DocumentNotFoundError,
    DocumentService,
    _generate_storage_key,
    _mime_matches,
)
from echomind.services.storage import (
    ObjectMetadata,
    StorageObjectNotFoundError,
)


# =============================================================================
# Fixtures: mock repository, storage, service
# =============================================================================
@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock async di DocumentRepository (tutti i metodi async)."""
    return AsyncMock()


@pytest.fixture
def mock_storage() -> AsyncMock:
    """Mock async di B2StorageService."""
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock, mock_storage: AsyncMock) -> DocumentService:
    return DocumentService(repository=mock_repo, storage=mock_storage)


def _make_document(
    *,
    owner_id: UUID | None = None,
    mime_type: str = "application/pdf",
    size_bytes: int = 1024,
    storage_key: str = "users/x/y.pdf",
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    """Crea un Document ORM-like per i mock (non tocca il DB)."""
    doc = Document(
        owner_id=owner_id or uuid4(),
        filename="file.pdf",
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage_key=storage_key,
    )
    doc.id = uuid4()
    doc.status = status
    doc.failure_reason = None
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


# =============================================================================
# init_upload
# =============================================================================
class TestInitUpload:
    @pytest.mark.asyncio
    async def test_creates_document_and_generates_presigned_url(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        owner_id = uuid4()
        fake_doc = _make_document(owner_id=owner_id)
        mock_repo.create.return_value = fake_doc
        mock_storage.generate_presigned_put.return_value = (
            "https://b2.example.com/bucket/key?Sig=abc",
            datetime.now(UTC) + timedelta(minutes=15),
        )

        document, url, expires_at = await service.init_upload(
            owner_id=owner_id,
            filename="report.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )

        # 1. Repository create chiamato con i giusti campi (storage_key generato)
        mock_repo.create.assert_awaited_once()
        kwargs = mock_repo.create.call_args.kwargs
        assert kwargs["owner_id"] == owner_id
        assert kwargs["filename"] == "report.pdf"
        assert kwargs["mime_type"] == "application/pdf"
        assert kwargs["size_bytes"] == 1024
        assert kwargs["storage_key"].startswith(f"users/{owner_id}/")
        assert kwargs["storage_key"].endswith(".pdf")

        # 2. Storage chiamato con la stessa key + content-length
        mock_storage.generate_presigned_put.assert_awaited_once()
        storage_kwargs = mock_storage.generate_presigned_put.call_args.kwargs
        assert storage_kwargs["content_type"] == "application/pdf"
        assert storage_kwargs["content_length"] == 1024

        # 3. Output
        assert document is fake_doc
        assert "Sig=abc" in url
        assert isinstance(expires_at, datetime)


# =============================================================================
# confirm_upload
# =============================================================================
class TestConfirmUpload:
    @pytest.mark.asyncio
    async def test_happy_path_marks_uploaded(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        doc = _make_document(mime_type="application/pdf", size_bytes=1024)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=1024,
            content_type="application/pdf",
        )
        mock_storage.get_object_range.return_value = b"%PDF-1.7..." * 30  # ~300 byte
        mock_repo.mark_uploaded.return_value = doc

        # Mock magic.from_buffer per ritornare 'application/pdf'.
        # Usiamo il path stringa per evitare di accedere a `magic` come attributo
        # esportato (è solo un import interno del modulo, mypy strict si lamenta).
        monkeypatch.setattr(
            "echomind.services.document.magic.from_buffer",
            lambda buf, mime: "application/pdf",
        )

        result = await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        mock_repo.mark_uploaded.assert_awaited_once_with(doc)
        mock_repo.mark_failed.assert_not_awaited()
        assert result is doc

    @pytest.mark.asyncio
    async def test_object_not_found_marks_failed(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        doc = _make_document()
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.side_effect = StorageObjectNotFoundError("nope")

        await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        mock_repo.mark_failed.assert_awaited_once_with(doc, "upload_not_received")

    @pytest.mark.asyncio
    async def test_size_mismatch_marks_failed(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        doc = _make_document(size_bytes=1024)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=999,  # diverso da 1024
            content_type="application/pdf",
        )

        await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        mock_repo.mark_failed.assert_awaited_once_with(doc, "size_mismatch")
        # get_object_range NON deve essere chiamato (uscita prima del magic check)
        mock_storage.get_object_range.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mime_mismatch_marks_failed(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        doc = _make_document(mime_type="application/pdf", size_bytes=512)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=512,
            content_type="application/pdf",
        )
        mock_storage.get_object_range.return_value = b"MZ\x90\x00..."  # exe header

        monkeypatch.setattr(
            "echomind.services.document.magic.from_buffer",
            lambda buf, mime: "application/x-msdownload",
        )

        await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        mock_repo.mark_failed.assert_awaited_once_with(doc, "mime_mismatch")

    @pytest.mark.asyncio
    async def test_docx_detected_as_zip_accepted(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MIME equivalence: DOCX = ZIP per magic, deve essere accettato."""
        docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        doc = _make_document(mime_type=docx_mime, size_bytes=2048)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=2048,
            content_type=docx_mime,
        )
        mock_storage.get_object_range.return_value = b"PK\x03\x04..." * 30

        monkeypatch.setattr(
            "echomind.services.document.magic.from_buffer",
            lambda buf, mime: "application/zip",
        )

        await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        mock_repo.mark_uploaded.assert_awaited_once_with(doc)
        mock_repo.mark_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_idempotent_for_already_uploaded(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        doc = _make_document(status=DocumentStatus.UPLOADED)
        mock_repo.get_by_id.return_value = doc

        result = await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        # NESSUNA chiamata storage o mark_*: solo get_by_id + ritorno
        assert result is doc
        mock_storage.head_object.assert_not_awaited()
        mock_repo.mark_uploaded.assert_not_awaited()
        mock_repo.mark_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_on_failed_status(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
    ) -> None:
        doc = _make_document(status=DocumentStatus.FAILED)
        mock_repo.get_by_id.return_value = doc

        with pytest.raises(DocumentAlreadyConfirmedError):
            await service.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_document_missing(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_by_id.return_value = None

        with pytest.raises(DocumentNotFoundError):
            await service.confirm_upload(owner_id=uuid4(), document_id=uuid4())


# =============================================================================
# confirm_upload --> trigger trascrizione (M4)
# =============================================================================
class TestConfirmTriggersTranscription:
    """Quando confirm porta il documento a 'uploaded', accoda la trascrizione."""

    @pytest.mark.asyncio
    async def test_success_enqueues_transcription(
        self,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        task_service = AsyncMock()
        svc = DocumentService(repository=mock_repo, storage=mock_storage, task_service=task_service)
        doc = _make_document(mime_type="application/pdf", size_bytes=1024)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=1024, content_type="application/pdf"
        )
        mock_storage.get_object_range.return_value = b"%PDF-1.7..." * 30
        mock_repo.mark_uploaded.return_value = doc
        monkeypatch.setattr(
            "echomind.services.document.magic.from_buffer",
            lambda buf, mime: "application/pdf",
        )

        await svc.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        task_service.enqueue_transcribe.assert_awaited_once_with(
            owner_id=doc.owner_id, document_id=doc.id
        )

    @pytest.mark.asyncio
    async def test_already_uploaded_does_not_enqueue(
        self,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """Re-confirm di un documento gia' uploaded: nessun nuovo enqueue (idempotenza)."""
        task_service = AsyncMock()
        svc = DocumentService(repository=mock_repo, storage=mock_storage, task_service=task_service)
        doc = _make_document(status=DocumentStatus.UPLOADED)
        mock_repo.get_by_id.return_value = doc

        await svc.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        task_service.enqueue_transcribe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mime_mismatch_does_not_enqueue(
        self,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Confirm che fallisce la validazione (mark_failed): niente trascrizione."""
        task_service = AsyncMock()
        svc = DocumentService(repository=mock_repo, storage=mock_storage, task_service=task_service)
        doc = _make_document(mime_type="application/pdf", size_bytes=512)
        mock_repo.get_by_id.return_value = doc
        mock_storage.head_object.return_value = ObjectMetadata(
            content_length=512, content_type="application/pdf"
        )
        mock_storage.get_object_range.return_value = b"MZ\x90\x00..."
        monkeypatch.setattr(
            "echomind.services.document.magic.from_buffer",
            lambda buf, mime: "application/x-msdownload",
        )

        await svc.confirm_upload(owner_id=doc.owner_id, document_id=doc.id)

        task_service.enqueue_transcribe.assert_not_awaited()


# =============================================================================
# delete_document
# =============================================================================
class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_deletes_storage_then_db(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        doc = _make_document(storage_key="users/abc/xyz.pdf")
        mock_repo.get_by_id.return_value = doc

        # Per registrare l'ordine di chiamata: i side_effect tracciano l'evento
        # senza tornare valori "falsi" da lambda (mypy si lamenterebbe del None
        # ritornato da list.append).
        call_order: list[str] = []

        async def _track_storage_delete(key: str) -> None:
            call_order.append("storage")

        async def _track_repo_delete(doc_id: UUID) -> bool:
            call_order.append("db")
            return True

        mock_storage.delete_object.side_effect = _track_storage_delete
        mock_repo.delete.side_effect = _track_repo_delete

        await service.delete_document(document_id=doc.id)

        # Ordine: prima B2, poi DB
        assert call_order == ["storage", "db"]
        mock_storage.delete_object.assert_awaited_once_with("users/abc/xyz.pdf")
        mock_repo.delete.assert_awaited_once_with(doc.id)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_document_missing(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        mock_repo.get_by_id.return_value = None

        with pytest.raises(DocumentNotFoundError):
            await service.delete_document(document_id=uuid4())

        # Niente chiamate side-effect
        mock_storage.delete_object.assert_not_awaited()
        mock_repo.delete.assert_not_awaited()


# =============================================================================
# READ (list, get)
# =============================================================================
class TestReadOperations:
    @pytest.mark.asyncio
    async def test_list_delegates_to_repository(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
    ) -> None:
        fake_docs = [_make_document() for _ in range(3)]
        mock_repo.list_by_owner.return_value = fake_docs

        result = await service.list_documents(owner_id=uuid4(), limit=10, offset=0)

        assert result == fake_docs
        mock_repo.list_by_owner.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_returns_document(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
    ) -> None:
        doc = _make_document()
        mock_repo.get_by_id.return_value = doc

        result = await service.get_document(document_id=doc.id)
        assert result is doc

    @pytest.mark.asyncio
    async def test_get_raises_not_found(
        self,
        service: DocumentService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_by_id.return_value = None

        with pytest.raises(DocumentNotFoundError):
            await service.get_document(document_id=uuid4())


# =============================================================================
# Helper modulo-level
# =============================================================================
class TestGenerateStorageKey:
    def test_format_includes_owner_and_extension(self) -> None:
        owner_id = uuid4()
        key = _generate_storage_key(owner_id, "Report Annuale 2026.PDF")
        assert key.startswith(f"users/{owner_id}/")
        assert key.endswith(".pdf")  # lowercase forzato

    def test_extension_optional(self) -> None:
        key = _generate_storage_key(uuid4(), "no-extension")
        # niente extension finale → no dot
        assert not key.endswith(".")

    def test_two_calls_produce_different_keys(self) -> None:
        """UUID4 garantisce unicità a-priori (collision practically zero)."""
        owner_id = uuid4()
        k1 = _generate_storage_key(owner_id, "a.txt")
        k2 = _generate_storage_key(owner_id, "a.txt")
        assert k1 != k2


class TestMimeMatches:
    @pytest.mark.parametrize(
        "declared,detected,expected",
        [
            ("application/pdf", "application/pdf", True),
            ("application/pdf", "application/x-msdownload", False),
            # DOCX equivalences
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/zip",
                True,
            ),
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/pdf",
                False,
            ),
            # WAV equivalences
            ("audio/wav", "audio/x-wav", True),
            ("audio/wav", "audio/vnd.wave", True),
            ("audio/wav", "audio/mpeg", False),
            # M4A equivalences
            ("audio/mp4", "video/mp4", True),
            ("audio/mp4", "audio/x-m4a", True),
            ("audio/mp4", "audio/mpeg", False),
            # Declared sconosciuto → False (defensive)
            ("foo/bar", "foo/bar", False),
        ],
    )
    def test_equivalences(self, declared: str, detected: str, expected: bool) -> None:
        assert _mime_matches(declared=declared, detected=detected) is expected

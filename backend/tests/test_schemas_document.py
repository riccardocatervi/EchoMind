"""Test degli schemas Pydantic per la risorsa Document.

Verifica:
- DocumentInitUpload: whitelist MIME, size > 0, filename 1-255, extra='forbid'
- DocumentRead: from_attributes funziona da oggetti SQLAlchemy-like
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from echomind.db.models import DocumentStatus
from echomind.schemas.document import (
    ALLOWED_MIME_TYPES,
    DocumentInitUpload,
    DocumentInitUploadResponse,
    DocumentRead,
)


# =============================================================================
# DocumentInitUpload — input validation
# =============================================================================
class TestDocumentInitUpload:
    """Coverage completa dei validator del payload di upload."""

    def test_valid_pdf_payload_passes(self) -> None:
        payload = DocumentInitUpload(
            filename="report.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )
        assert payload.filename == "report.pdf"
        assert payload.mime_type == "application/pdf"
        assert payload.size_bytes == 1024

    @pytest.mark.parametrize("mime", sorted(ALLOWED_MIME_TYPES))
    def test_all_whitelisted_mimes_accepted(self, mime: str) -> None:
        """Ogni MIME in whitelist passa la validazione."""
        payload = DocumentInitUpload(
            filename="file",
            mime_type=mime,
            size_bytes=1,
        )
        assert payload.mime_type == mime

    @pytest.mark.parametrize(
        "bad_mime",
        [
            "application/x-msdownload",  # exe
            "image/png",  # immagine (non in scope M2)
            "video/mp4",  # video
            "application/zip",
            "text/html",
            "",
            "not-a-mime",
        ],
    )
    def test_non_whitelisted_mime_rejected(self, bad_mime: str) -> None:
        with pytest.raises(ValidationError):
            DocumentInitUpload(
                filename="file",
                mime_type=bad_mime,
                size_bytes=1,
            )

    @pytest.mark.parametrize("size", [0, -1, -1000])
    def test_size_must_be_positive(self, size: int) -> None:
        with pytest.raises(ValidationError):
            DocumentInitUpload(
                filename="f",
                mime_type="application/pdf",
                size_bytes=size,
            )

    def test_filename_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DocumentInitUpload(
                filename="x" * 256,
                mime_type="application/pdf",
                size_bytes=1,
            )

    def test_empty_filename_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DocumentInitUpload(
                filename="",
                mime_type="application/pdf",
                size_bytes=1,
            )

    def test_extra_fields_forbidden(self) -> None:
        """Typo client (camelCase invece di snake_case) → ValidationError."""
        with pytest.raises(ValidationError):
            DocumentInitUpload.model_validate(
                {
                    "filename": "f.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1,
                    "fileName": "extra",  # typo: rifiutato da extra='forbid'
                }
            )


# =============================================================================
# DocumentRead — output schema, conversione da ORM-like
# =============================================================================
class TestDocumentRead:
    def test_from_orm_like_object(self) -> None:
        """from_attributes=True legge da oggetti con gli attributi giusti."""
        now = datetime.now(UTC)
        fake_orm = SimpleNamespace(
            id=uuid4(),
            owner_id=uuid4(),
            filename="document.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            status=DocumentStatus.UPLOADED,
            failure_reason=None,
            created_at=now,
            updated_at=now,
            # Campi extra NON dovrebbero dare problemi: from_attributes legge solo
            # i campi dichiarati nello schema.
            storage_key="should-not-be-exposed",
        )

        read = DocumentRead.model_validate(fake_orm)
        assert read.filename == "document.pdf"
        assert read.status == DocumentStatus.UPLOADED
        assert read.failure_reason is None

    def test_storage_key_not_exposed(self) -> None:
        """storage_key è dettaglio implementativo: NON deve apparire in DocumentRead."""
        assert "storage_key" not in DocumentRead.model_fields

    def test_failed_status_with_reason(self) -> None:
        now = datetime.now(UTC)
        fake_orm = SimpleNamespace(
            id=uuid4(),
            owner_id=uuid4(),
            filename="bad.exe",
            mime_type="application/pdf",  # client ha mentito
            size_bytes=100,
            status=DocumentStatus.FAILED,
            failure_reason="mime_mismatch",
            created_at=now,
            updated_at=now,
            storage_key="x",
        )
        read = DocumentRead.model_validate(fake_orm)
        assert read.status == DocumentStatus.FAILED
        assert read.failure_reason == "mime_mismatch"


# =============================================================================
# DocumentInitUploadResponse — output schema POST /documents
# =============================================================================
class TestDocumentInitUploadResponse:
    def test_construct_with_all_fields(self) -> None:
        doc_id = uuid4()
        expires = datetime.now(UTC)
        response = DocumentInitUploadResponse(
            document_id=doc_id,
            upload_url="https://s3.example.com/bucket/key?X-Amz-Sig=abc",
            expires_at=expires,
        )
        assert response.document_id == doc_id
        assert "X-Amz-Sig=abc" in response.upload_url
        assert response.expires_at == expires

"""Pydantic schemas per la risorsa Document.

Convenzione naming (CQS):
- `DocumentRead`               → ciò che l'API RITORNA (output GET, list)
- `DocumentInitUpload`         → ciò che l'API ACCETTA (input POST /documents)
- `DocumentInitUploadResponse` → output di POST /documents (id + upload URL)

La whitelist `ALLOWED_MIME_TYPES` è la **single source of truth** per i tipi
file accettati. Usata in:
1. Validazione input (questo file)
2. Documentazione OpenAPI (FastAPI legge i Literal/constraint dei field)
3. Service post-upload (`document.py` Step 6) per confronto MIME dichiarato
   vs MIME rilevato con magic bytes
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echomind.db.models import DocumentStatus

# -----------------------------------------------------------------------------
# Whitelist MIME types accettati in M2
# -----------------------------------------------------------------------------
# Frozen set: immutabile, hash O(1) per il lookup. Definita modulo-level per
# essere importabile da services/, tests/, docs.
#
# Scope M2:
#   - Documenti: PDF, DOCX, TXT
#   - Audio: MP3, WAV, M4A
#
# Aggiungere un MIME qui = aggiunge il supporto in tutta l'app + tests.
ALLOWED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        # Documenti
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
        "text/plain",
        # Audio
        "audio/mpeg",  # MP3 standard
        "audio/wav",  # WAV (alcuni server)
        "audio/x-wav",  # WAV (alternativa diffusa)
        "audio/mp4",  # M4A (container MP4 + audio)
        "audio/x-m4a",  # M4A (alternativa)
    }
)


# -----------------------------------------------------------------------------
# Field type alias riusabili
# -----------------------------------------------------------------------------
# Filename: 1-255 char (limite POSIX) e niente caratteri di controllo
FilenameField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        description="Nome originale del file. 1-255 caratteri.",
    ),
]


# -----------------------------------------------------------------------------
# Input schema: POST /api/v1/documents
# -----------------------------------------------------------------------------
class DocumentInitUpload(BaseModel):
    """Payload per inizializzare un upload.

    Il client dichiara filename, MIME e size attesi. L'app crea la riga,
    genera presigned URL B2 con `Content-Length` constraint, e ritorna
    `DocumentInitUploadResponse`.

    NB: il MIME qui è solo **dichiarato dal client**. La verifica vera
    avviene server-side dopo l'upload (Step 6, `DocumentService.confirm_upload`).
    """

    filename: FilenameField
    mime_type: str = Field(
        description=(
            "MIME type dichiarato. Deve essere uno della whitelist applicativa "
            "(vedi ALLOWED_MIME_TYPES). Verificato server-side post-upload."
        ),
    )
    size_bytes: int = Field(
        gt=0,
        description="Dimensione attesa in bytes. Verificata HEAD post-upload.",
    )

    # `extra='forbid'`: rifiuta payload con campi extra (typo client → 422).
    model_config = ConfigDict(extra="forbid")

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_in_whitelist(cls, v: str) -> str:
        """Rifiuta MIME non in whitelist. Errore esplicito per debugging client."""
        if v not in ALLOWED_MIME_TYPES:
            allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
            raise ValueError(f"mime_type '{v}' non supportato. Accettati: {allowed}")
        return v


# -----------------------------------------------------------------------------
# Output schemas
# -----------------------------------------------------------------------------
class DocumentInitUploadResponse(BaseModel):
    """Risposta di POST /documents — il client usa upload_url per inviare a B2."""

    document_id: UUID = Field(description="ID interno del documento appena creato.")
    upload_url: str = Field(
        description="Presigned URL PUT verso B2. Scade dopo upload_presign_ttl_seconds.",
    )
    expires_at: datetime = Field(
        description="Scadenza assoluta della upload_url (UTC).",
    )


class DocumentRead(BaseModel):
    """Vista del documento esposta dall'API.

    NB: NON esponiamo `storage_key`. È un dettaglio implementativo
    server-side. Se mai esponessimo download, sarebbe via un altro
    presigned URL GET, non rivelando la chiave diretta.
    """

    id: UUID
    owner_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

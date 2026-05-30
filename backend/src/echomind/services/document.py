"""DocumentService — orchestrazione del lifecycle upload.

Connessione di tre risorse:
- DocumentRepository (DB sotto RLS)
- B2StorageService   (object storage S3-compatible)
- python-magic       (MIME detection via magic bytes)

Lifecycle handling:
    init_upload     → INSERT pending, presigned URL
    confirm_upload  → HEAD + magic bytes + UPDATE status (uploaded | failed)
    list/get        → READ via repository
    delete_document → DELETE B2 object + DELETE riga DB (idempotente)

NB: il service NON conosce FastAPI / HTTP. È riutilizzabile da CLI, worker
Celery (M3), test. Solo l'endpoint conosce HTTP.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Final
from uuid import UUID

import magic

from echomind.core.logging import get_logger
from echomind.db.models import Document
from echomind.db.repositories import DocumentRepository
from echomind.services.storage import (
    B2StorageService,
    StorageObjectNotFoundError,
)

log = get_logger(__name__)


# -----------------------------------------------------------------------------
# Errori di dominio (mappati a HTTP da api/deps.py o exception handlers)
# -----------------------------------------------------------------------------
class DocumentError(Exception):
    """Base class per errori del lifecycle documento."""


class DocumentNotFoundError(DocumentError):
    """Il documento non esiste (o RLS lo nasconde) per l'utente corrente."""


class DocumentAlreadyConfirmedError(DocumentError):
    """confirm_upload chiamato su un documento già 'uploaded' o 'failed'."""


# -----------------------------------------------------------------------------
# MIME equivalence map
# -----------------------------------------------------------------------------
# Per ogni MIME dichiarato dal client, il set di MIME "accettabili" che magic
# può detectare e confermarlo. Se il MIME rilevato NON è nel set --> mismatch.
#
# Lessons learned:
# - DOCX è uno ZIP archive con XML dentro: magic ritorna 'application/zip'
# - WAV ha alias storici: audio/wav, audio/x-wav, audio/vnd.wave
# - M4A condivide il container con MP4 video: magic può ritornare 'video/mp4'
MIME_EQUIVALENCES: Final[dict[str, frozenset[str]]] = {
    "application/pdf": frozenset({"application/pdf"}),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    "text/plain": frozenset({"text/plain"}),
    "audio/mpeg": frozenset({"audio/mpeg"}),
    "audio/wav": frozenset({"audio/wav", "audio/x-wav", "audio/vnd.wave"}),
    "audio/x-wav": frozenset({"audio/wav", "audio/x-wav", "audio/vnd.wave"}),
    "audio/mp4": frozenset({"audio/mp4", "audio/x-m4a", "video/mp4"}),
    "audio/x-m4a": frozenset({"audio/mp4", "audio/x-m4a", "video/mp4"}),
}


# Quanti byte scaricare per il magic-bytes detection.
# 256 byte sono sufficienti per identificare 99% dei formati.
# Costo: 1 GET range per documento, ~0.2 KB di banda B2 per confirm.
MAGIC_BYTES_TO_FETCH: Final[int] = 256


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class DocumentService:
    """Orchestrazione del lifecycle Document.

    Riceve:
    - repository: opera nella sessione RLS-bound dell'utente
    - storage:    client S3-compatible (in dev test: moto)
    """

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: B2StorageService,
    ) -> None:
        self._repository = repository
        self._storage = storage

    # -------------------------------------------------------------------------
    # init_upload
    # -------------------------------------------------------------------------
    async def init_upload(
        self,
        *,
        owner_id: UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
    ) -> tuple[Document, str, datetime]:
        """Step 1-3 del flow: crea row pending + presigned URL.

        Returns:
            (document_orm, upload_url, expires_at)
        """
        storage_key = _generate_storage_key(owner_id, filename)

        # 1. INSERT documents(status=pending). Sotto RLS la policy
        #    `document_insert_own` permette solo se owner_id == sub_claim.
        document = await self._repository.create(
            owner_id=owner_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )

        # 2. Genera presigned URL PUT con vincolo Content-Length.
        upload_url, expires_at = await self._storage.generate_presigned_put(
            storage_key,
            content_type=mime_type,
            content_length=size_bytes,
        )

        log.info(
            "document_init_upload",
            document_id=str(document.id),
            owner_id=str(owner_id),
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        return document, upload_url, expires_at

    # -------------------------------------------------------------------------
    # confirm_upload
    # -------------------------------------------------------------------------
    async def confirm_upload(self, *, owner_id: UUID, document_id: UUID) -> Document:
        """Step 5-9: HEAD + magic-bytes + UPDATE status.

        Idempotente per documenti già 'uploaded': ritorna lo stato corrente
        senza ri-validare. Per 'failed': solleva DocumentAlreadyConfirmedError
        (re-tentativo richiede una nuova init_upload).

        Esiti:
        - HEAD non trova object   → mark_failed('upload_not_received')
        - size diversa            → mark_failed('size_mismatch')
        - MIME impostore          → mark_failed('mime_mismatch')
        - tutto ok                → mark_uploaded
        """
        document = await self._require_document(document_id)

        # Idempotency: se già uploaded, ritorna senza ri-validare.
        if document.status.value == "uploaded":
            return document
        if document.status.value == "failed":
            raise DocumentAlreadyConfirmedError(
                f"Document {document_id} è in stato 'failed'. "
                "Avvia una nuova init_upload per ritentare."
            )

        # 1. HEAD: verifica che l'object esista e size matchi.
        try:
            meta = await self._storage.head_object(document.storage_key)
        except StorageObjectNotFoundError:
            log.warning(
                "document_confirm_no_object",
                document_id=str(document_id),
                storage_key=document.storage_key,
            )
            return await self._repository.mark_failed(document, "upload_not_received")

        if meta.content_length != document.size_bytes:
            log.warning(
                "document_confirm_size_mismatch",
                document_id=str(document_id),
                declared=document.size_bytes,
                actual=meta.content_length,
            )
            return await self._repository.mark_failed(document, "size_mismatch")

        # 2. Scarica i primi 256 byte --> magic detection.
        head_bytes = await self._storage.get_object_range(
            document.storage_key,
            start=0,
            end_inclusive=MAGIC_BYTES_TO_FETCH - 1,
        )
        detected_mime = await asyncio.to_thread(
            magic.from_buffer,
            head_bytes,
            True,  # mime=True (positional, evita kwargs noise)
        )

        # 3. Confronto con whitelist di equivalenze
        if not _mime_matches(declared=document.mime_type, detected=detected_mime):
            log.warning(
                "document_confirm_mime_mismatch",
                document_id=str(document_id),
                declared=document.mime_type,
                detected=detected_mime,
            )
            return await self._repository.mark_failed(document, "mime_mismatch")

        # 4. All clear: status='uploaded'
        result = await self._repository.mark_uploaded(document)
        log.info(
            "document_confirm_uploaded",
            document_id=str(document_id),
            detected_mime=detected_mime,
        )
        return result

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    async def list_documents(
        self,
        *,
        owner_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        """Lista paginata dei documenti dell'utente, ordinati dal più recente."""
        return await self._repository.list_by_owner(owner_id, limit=limit, offset=offset)

    async def get_document(self, *, document_id: UUID) -> Document:
        """Dettaglio singolo. Solleva DocumentNotFoundError se assente/nascosto da RLS."""
        return await self._require_document(document_id)

    # -------------------------------------------------------------------------
    # DELETE (B2 + DB, ordine deliberato)
    # -------------------------------------------------------------------------
    async def delete_document(self, *, document_id: UUID) -> None:
        """Hard delete: prima B2 object, poi DB row.

        Idempotente:
        - B2 DELETE su key inesistente è no-op (vedi storage.delete_object)
        - DB DELETE su id inesistente ritorna False (vedi repository.delete)

        Se DB fallisce dopo B2 OK: il client può rieseguire il DELETE,
        l'idempotenza garantisce safety.
        """
        document = await self._require_document(document_id)

        await self._storage.delete_object(document.storage_key)
        await self._repository.delete(document_id)

        log.info(
            "document_deleted",
            document_id=str(document_id),
            storage_key=document.storage_key,
        )

    # -------------------------------------------------------------------------
    # Helper interno
    # -------------------------------------------------------------------------
    async def _require_document(self, document_id: UUID) -> Document:
        """get + raise se None. Sotto RLS: ritorna None anche per documenti di altri."""
        document = await self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return document


# -----------------------------------------------------------------------------
# Funzioni helper modulo-level
# -----------------------------------------------------------------------------
def _generate_storage_key(owner_id: UUID, filename: str) -> str:
    """Genera la chiave B2 per l'oggetto.

    Format: `users/{owner_id}/{uuid4}{ext}`
    - prefix per owner: comodo per audit/cleanup massivo via B2 console
    - uuid4: niente collision, niente enumeration attack
    - ext preservata: B2 dashboard mostra la categoria corretta, niente
      impatto sulla sicurezza (RLS + presigned URL non vedono l'ext)
    """
    _, ext = os.path.splitext(filename)
    ext = ext.lower() if ext else ""
    return f"users/{owner_id}/{uuid.uuid4()}{ext}"


def _mime_matches(*, declared: str, detected: str) -> bool:
    """Confronta MIME dichiarato con quello rilevato, considerando le equivalenze.

    Ritorna True se il rilevato è in `MIME_EQUIVALENCES[declared]`.
    Se il declared non è in mappa (dovrebbe essere stato rifiutato dallo schema
    Pydantic, ma defensive coding) → False.
    """
    allowed = MIME_EQUIVALENCES.get(declared, frozenset())
    return detected in allowed

"""Endpoint /documents — gestione del lifecycle di upload utente.

5 endpoint:
- POST   /api/v1/documents                   → init upload (genera presigned URL)
- POST   /api/v1/documents/{id}/confirm      → conferma upload + valida MIME
- GET    /api/v1/documents                   → lista paginata (RLS-filtered)
- GET    /api/v1/documents/{id}              → dettaglio
- DELETE /api/v1/documents/{id}              → hard delete (B2 + DB)

Tutta la business logic vive nei layer service/repository.
Qui solo:
- Validazione body via Pydantic schemas
- Mapping HTTP query params → service args
- Conversione Document ORM → DocumentRead schema
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from echomind.api.deps import DocumentServiceDep, UserIdDep
from echomind.schemas.document import (
    DocumentInitUpload,
    DocumentInitUploadResponse,
    DocumentRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])


# -----------------------------------------------------------------------------
# Init upload
# -----------------------------------------------------------------------------
@router.post(
    "",
    response_model=DocumentInitUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Inizializza un upload (genera presigned URL B2)",
    description=(
        "Crea il record `documents` in stato `pending` e ritorna un presigned URL "
        "PUT verso B2. Il client deve poi caricare il file direttamente con "
        "`PUT <upload_url>` rispettando Content-Type e Content-Length. "
        "Dopo l'upload, chiama POST /documents/{id}/confirm per validare."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        403: {"description": "Claim JWT mancante"},
        422: {"description": "Payload malformato o MIME non in whitelist"},
        503: {"description": "Storage backend non configurato"},
    },
)
async def init_upload(
    user_id: UserIdDep,
    payload: DocumentInitUpload,
    service: DocumentServiceDep,
) -> DocumentInitUploadResponse:
    document, upload_url, expires_at = await service.init_upload(
        owner_id=user_id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
    )
    return DocumentInitUploadResponse(
        document_id=document.id,
        upload_url=upload_url,
        expires_at=expires_at,
    )


# -----------------------------------------------------------------------------
# Confirm upload
# -----------------------------------------------------------------------------
@router.post(
    "/{document_id}/confirm",
    response_model=DocumentRead,
    status_code=status.HTTP_200_OK,
    summary="Conferma upload completato (valida MIME server-side)",
    description=(
        "HEAD object su B2, scarica i primi 256 byte, verifica MIME via magic bytes. "
        "Esiti: status=uploaded (ok) o failed (mismatch). "
        "Idempotente per documenti già `uploaded`; 409 per documenti `failed`."
    ),
    responses={
        401: {"description": "Token mancante/invalido"},
        404: {"description": "Documento non trovato o non tuo"},
        409: {"description": "Documento già confermato come failed"},
        503: {"description": "Storage non disponibile"},
    },
)
async def confirm_upload(
    user_id: UserIdDep,
    document_id: UUID,
    service: DocumentServiceDep,
) -> DocumentRead:
    document = await service.confirm_upload(
        owner_id=user_id,
        document_id=document_id,
    )
    return DocumentRead.model_validate(document)


# -----------------------------------------------------------------------------
# List
# -----------------------------------------------------------------------------
@router.get(
    "",
    response_model=list[DocumentRead],
    summary="Lista paginata dei propri documenti",
    description="Ordinati dal più recente. Sfrutta indice composito `(owner_id, created_at DESC)`.",
)
async def list_documents(
    user_id: UserIdDep,
    service: DocumentServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="Max risultati (1-100)")] = 20,
    offset: Annotated[int, Query(ge=0, description="Skip dei primi N")] = 0,
) -> list[DocumentRead]:
    documents = await service.list_documents(owner_id=user_id, limit=limit, offset=offset)
    return [DocumentRead.model_validate(d) for d in documents]


# -----------------------------------------------------------------------------
# Detail
# -----------------------------------------------------------------------------
@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Dettaglio di un documento",
    responses={404: {"description": "Documento non trovato (o nascosto da RLS)"}},
)
async def get_document(
    user_id: UserIdDep,
    document_id: UUID,
    service: DocumentServiceDep,
) -> DocumentRead:
    document = await service.get_document(document_id=document_id)
    return DocumentRead.model_validate(document)


# -----------------------------------------------------------------------------
# Delete
# -----------------------------------------------------------------------------
@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard delete (B2 object + DB row)",
    description=(
        "Idempotente. Ordine: prima B2 object, poi DB row. "
        "Se DB fallisce dopo B2 OK, il client può riprovare safely."
    ),
    responses={
        204: {"description": "Cancellato (no content)"},
        404: {"description": "Documento non trovato"},
    },
)
async def delete_document(
    user_id: UserIdDep,
    document_id: UUID,
    service: DocumentServiceDep,
) -> None:
    await service.delete_document(document_id=document_id)

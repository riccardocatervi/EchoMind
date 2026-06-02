"""SummaryService -- lettura dei riassunti (output di KnowledgeExtraction, M5).

I riassunti li SCRIVE il worker (sessione di sistema); l'API li espone in SOLA
LETTURA, filtrati per-utente da RLS (policy `summary_select_own`). Service sottile:
una READ con traduzione None --> SummaryNotFoundError (--> 404). Gemello di
TranscriptService.
"""

from __future__ import annotations

from uuid import UUID

from echomind.db.models import Summary
from echomind.db.repositories import SummaryRepository


# -----------------------------------------------------------------------------
# Errori di dominio (mappati a HTTP dagli exception handler in main.py)
# -----------------------------------------------------------------------------
class SummaryError(Exception):
    """Base per gli errori del dominio Summary."""


class SummaryNotFoundError(SummaryError):
    """Nessun riassunto per quel documento: non ancora pronto (in elaborazione),
    fallito, oppure RLS lo nasconde (documento di un altro utente)."""


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class SummaryService:
    """Lettura dei riassunti dell'utente (sessione RLS-bound)."""

    def __init__(self, *, repository: SummaryRepository) -> None:
        self._repository = repository

    async def get_by_document(self, *, document_id: UUID) -> Summary:
        """Ritorna il riassunto di un documento.

        Raises:
            SummaryNotFoundError: se assente. Sotto RLS: assente anche se esiste ma
            appartiene a un altro utente (indistinguibile by design).
        """
        summary = await self._repository.get_by_document_id(document_id)
        if summary is None:
            raise SummaryNotFoundError(f"Summary for document {document_id} not found")
        return summary

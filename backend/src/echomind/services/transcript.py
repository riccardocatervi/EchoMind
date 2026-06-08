"""TranscriptService -- lettura dei transcript (output di MediaProcessing, M4).

I transcript li SCRIVE il worker (sessione di sistema); l'API li espone in SOLA
LETTURA, filtrati per-utente da RLS (policy `transcript_select_own`). Service
sottile: una READ con traduzione None --> TranscriptNotFoundError (--> 404).
"""

from __future__ import annotations

from uuid import UUID

from echomind.db.models import Transcript
from echomind.db.repositories import TranscriptRepository


# -----------------------------------------------------------------------------
# Errori di dominio (mappati a HTTP dagli exception handler in main.py)
# -----------------------------------------------------------------------------
class TranscriptError(Exception):
    """Base per gli errori del dominio Transcript."""


class TranscriptNotFoundError(TranscriptError):
    """Nessun transcript per quel documento: non ancora pronto (in elaborazione),
    fallito, oppure RLS lo nasconde (documento di un altro utente)."""


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class TranscriptService:
    """Lettura dei transcript dell'utente (sessione RLS-bound)."""

    def __init__(self, *, repository: TranscriptRepository) -> None:
        self._repository = repository

    async def get_by_document(self, *, document_id: UUID) -> Transcript:
        """Ritorna il transcript di un documento.

        Raises:
            TranscriptNotFoundError: se assente. Sotto RLS: assente anche se
            esiste ma appartiene a un altro utente (indistinguibile by design).
        """
        transcript = await self._repository.get_by_document_id(document_id)
        if transcript is None:
            raise TranscriptNotFoundError(f"Transcript for document {document_id} not found")
        return transcript

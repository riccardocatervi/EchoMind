"""Repository pattern: incapsula tutte le query su una tabella.

Convenzioni:
- Un modulo per repository (`profile.py`, in futuro `document.py`, ...)
- Ogni repository riceve la `AsyncSession` nel costruttore
- I metodi hanno nomi di dominio (`get_by_id`, `create`), non SQL
  (`select_where_id_equals`)

Niente import di FastAPI, Pydantic schemas o services qui: il repository
è il livello più basso "che parla col DB" e deve restare lightweight.
"""

from echomind.db.repositories.document import DocumentRepository
from echomind.db.repositories.embedding import EmbeddingRepository, EmbeddingValue, SimilarEntity
from echomind.db.repositories.profile import ProfileRepository
from echomind.db.repositories.summary import SummaryRepository
from echomind.db.repositories.task import TaskRepository
from echomind.db.repositories.transcript import TranscriptRepository

__all__ = [
    "DocumentRepository",
    "EmbeddingRepository",
    "EmbeddingValue",
    "ProfileRepository",
    "SimilarEntity",
    "SummaryRepository",
    "TaskRepository",
    "TranscriptRepository",
]

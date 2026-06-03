"""SQLAlchemy ORM models.

Convenzione:
- Un modulo per modello (`profile.py`, in futuro `document.py`, ecc.)
- Modelli importati qui per consentire ad Alembic di "vederli tutti"
  con un singolo `from echomind.db.models import *` nel suo env.py

Niente import qui di cose non-modello (services, repositories) per
evitare cicli import.
"""

from echomind.db.models.document import Document, DocumentStatus
from echomind.db.models.embedding import EntityEmbedding
from echomind.db.models.profile import Profile
from echomind.db.models.summary import Summary
from echomind.db.models.task import Task, TaskStatus, TaskType
from echomind.db.models.transcript import SourceType, Transcript

__all__ = [
    "Document",
    "DocumentStatus",
    "EntityEmbedding",
    "Profile",
    "SourceType",
    "Summary",
    "Task",
    "TaskStatus",
    "TaskType",
    "Transcript",
]

"""Service layer: business logic.

Convenzione:
- Un service per aggregate root del dominio (Profile, Document, ...)
- Service NON conosce FastAPI: API-agnostic, riutilizzabile da CLI/worker/test
- Service NON contiene query SQL: delega ai repository

Composizione tipica:
    ProfileService(repository=ProfileRepository(session))
"""

from echomind.services.document import (
    DocumentAlreadyConfirmedError,
    DocumentError,
    DocumentNotFoundError,
    DocumentService,
)
from echomind.services.profile import ProfileService
from echomind.services.storage import (
    B2StorageService,
    ObjectMetadata,
    StorageError,
    StorageObjectNotFoundError,
)

__all__ = [
    "B2StorageService",
    "DocumentAlreadyConfirmedError",
    "DocumentError",
    "DocumentNotFoundError",
    "DocumentService",
    "ObjectMetadata",
    "ProfileService",
    "StorageError",
    "StorageObjectNotFoundError",
]

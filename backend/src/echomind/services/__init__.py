"""Service layer: business logic.

Convenzione:
- Un service per aggregate root del dominio (Profile, Document, ...)
- Service NON conosce FastAPI: API-agnostic, riutilizzabile da CLI/worker/test
- Service NON contiene query SQL: delega ai repository

Composizione tipica:
    ProfileService(repository=ProfileRepository(session))
"""

from echomind.services.profile import ProfileService

__all__ = ["ProfileService"]

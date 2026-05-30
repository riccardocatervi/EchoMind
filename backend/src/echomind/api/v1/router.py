"""Router aggregato di API v1.

Collega tutti i sotto-router (`/health`, `/users`, `/profiles`, ...).
Punto unico di mounting in `main.py`.
"""

from __future__ import annotations

from fastapi import APIRouter

from echomind.api.v1 import documents, health, profiles, tasks, users

router = APIRouter(prefix="/api/v1")

# Registrazione sotto-router. Ordine: dal più semplice al più complesso.
router.include_router(health.router)
router.include_router(users.router)
router.include_router(profiles.router)
router.include_router(documents.router)
router.include_router(tasks.router)

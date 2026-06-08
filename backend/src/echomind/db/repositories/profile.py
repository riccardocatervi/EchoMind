"""Repository per la risorsa Profile.

Responsabilità ESCLUSIVA: query SQLAlchemy sulla tabella `profiles`.
NIENTE business logic ("just-in-time create"), NIENTE FastAPI, NIENTE
serializzazione. Solo CRUD primitives.

Le RLS policy del DB filtreranno automaticamente in base al claim JWT
settato da `set_rls_user()` nella sessione: questo repository NON deve
duplicare i filtri `WHERE user_id = ...`, è già gestito da Postgres.

Naming convention:
- `get_*`     → ritorna oggetto o None (read)
- `list_*`    → ritorna sequenza (read)
- `create_*`  → crea + ritorna (write)
- `update_*`  → modifica in place + ritorna (write)
- `delete_*`  → rimuove (write)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import Profile


class ProfileRepository:
    """Accesso CRUD alla tabella `profiles`.

    Pattern: una istanza per richiesta HTTP (la sessione è scoped per-request).
    Costruita in `services.profile.ProfileService.__init__`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> Profile | None:
        """Ritorna il profile dato il suo ID (= user_id Supabase), o None.

        Sotto RLS attiva, `user_id` può essere SOLO quello dell'utente
        autenticato — altri ID semplicemente non sono visibili (None).
        """
        result = await self._session.execute(select(Profile).where(Profile.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID, display_name: str | None = None) -> Profile:
        """Crea un nuovo profile.

        IMPORTANTE: la creazione del profile sotto RLS richiede che esista
        una policy INSERT che permetta `id == sub_claim`. In M1 NON l'abbiamo
        definita, perché il creator dev'essere `service_role` (= sessione
        non-RLS). Vedi `services.profile.ProfileService.get_or_create` per
        la strategia di gestione.
        """
        profile = Profile(id=user_id, display_name=display_name)
        self._session.add(profile)
        # flush: forza SQL INSERT ora, popola server-side defaults
        # (created_at, updated_at) sull'oggetto Python.
        await self._session.flush()
        # refresh: ricarica i valori from DB (i defaults appena calcolati)
        await self._session.refresh(profile)
        return profile

    async def update_display_name(self, profile: Profile, display_name: str | None) -> Profile:
        """Aggiorna display_name su un profile già attaccato alla sessione.

        Il trigger `profiles_updated_at` aggiornerà automaticamente updated_at.
        """
        profile.display_name = display_name
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def update_preferred_language(self, profile: Profile, language: str) -> Profile:
        """Aggiorna la lingua di output preferita su un profile in sessione.

        Il chiamante (service/schema) ha gia' validato `language` contro le
        lingue supportate. Il trigger `profiles_updated_at` tocca updated_at.
        """
        profile.preferred_language = language
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

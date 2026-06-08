"""Service layer per la risorsa Profile.

Business logic CHIAVE: just-in-time provisioning.
L'utente esiste in Supabase Auth (auth.users) ma potrebbe non avere ancora
un profile nel nostro DB. Lo creiamo lazy al primo accesso autenticato.

Architettura di sessioni richiesta:
    - Una sessione RLS-bound (`app_runtime`) per le query "own resource"
    - Una sessione non-RLS (privilegi `echomind`) per la creazione iniziale,
      perché la nostra policy INSERT in M1 è ASSENTE (vedi 0001_initial_schema)

Questo è coerente col pattern Supabase: i client API parlano come
`authenticated`, ma alcune operazioni "di sistema" (provisioning, signup
hook) usano `service_role`. Qui simuliamo entrambi i ruoli con due
sessioni distinte.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.core.logging import get_logger
from echomind.db.models import Profile
from echomind.db.repositories.profile import ProfileRepository

log = get_logger(__name__)


class ProfileService:
    """Orchestrazione business logic sui Profile.

    Riceve due dipendenze:
    - `repository`: opera nella sessione RLS-bound dell'utente (read/update)
    - `system_session_maker`: factory per aprire sessioni non-RLS
      (necessarie per il provisioning iniziale)
    """

    def __init__(
        self,
        repository: ProfileRepository,
        system_session_maker: async_sessionmaker[AsyncSession],
        *,
        seed_auth_user: bool = False,
    ) -> None:
        self._repository = repository
        self._system_session_maker = system_session_maker
        # Solo in sviluppo (vedi get_or_create). Default False = sicuro in produzione.
        self._seed_auth_user = seed_auth_user

    async def get_or_create(self, user_id: UUID) -> Profile:
        """Ritorna il profile dell'utente, creandolo se non esiste.

        Pattern just-in-time:
        1. Cerca via sessione RLS (vedrà solo il proprio profile, se esiste)
        2. Se non esiste, apre una sessione di sistema (non-RLS) e crea
        3. Rilegge via sessione RLS per coerenza (e per validare che ora esista)

        Concurrent first-access: se due richieste arrivano simultaneamente
        per lo stesso utente nuovo, la seconda otterrà IntegrityError sulla
        PK. Lo catchiamo e rileggiamo (idempotency naturale).
        """
        existing = await self._repository.get_by_id(user_id)
        if existing is not None:
            return existing

        # Provisioning con sessione non-RLS (privilegi di sistema)
        log.info("profile_just_in_time_create", user_id=str(user_id))
        try:
            async with (
                self._system_session_maker() as system_session,
                system_session.begin(),
            ):
                system_repository = ProfileRepository(system_session)
                # `get_by_id` come superuser: verifica race condition
                already_created = await system_repository.get_by_id(user_id)
                if already_created is None:
                    if self._seed_auth_user:
                        # SOLO in development: l'utente vive in Supabase cloud ma non
                        # nel Postgres locale, quindi la FK profiles -> auth.users
                        # fallirebbe. In produzione auth.users e' gestito da Supabase
                        # e questo ramo resta disattivato (flag False).
                        await system_session.execute(
                            text(
                                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT (id) DO NOTHING"
                            ),
                            {"id": str(user_id)},
                        )
                    await system_repository.create(user_id)
        except IntegrityError:
            # Race condition: tra il nostro check e l'INSERT, un'altra richiesta
            # concorrente per lo stesso utente nuovo ha gia' creato il profile
            # (PK violation). La transazione di sistema e' gia' rollbacked dal
            # context manager `begin()`. E' uno scenario benigno: il profile
            # ora esiste, quindi proseguiamo alla rilettura idempotente.
            log.info("profile_just_in_time_create_race_resolved", user_id=str(user_id))

        # Rilettura via sessione RLS dell'utente (per coerenza del path GET)
        profile = await self._repository.get_by_id(user_id)
        if profile is None:
            # Non dovrebbe mai succedere a questo punto: o esisteva già,
            # o l'abbiamo appena creato. Se accade, c'è un bug nelle RLS.
            raise RuntimeError(f"Profile {user_id} created but invisible via RLS — check policies")
        return profile

    async def update_display_name(self, user_id: UUID, display_name: str | None) -> Profile:
        """Aggiorna il display_name dell'utente corrente.

        Pre-requisito: il profile esiste (chiamare get_or_create prima).
        Sotto RLS: l'UPDATE è permesso SOLO se id == sub_claim.
        """
        profile = await self._repository.get_by_id(user_id)
        if profile is None:
            raise RuntimeError(f"Profile {user_id} not found — call get_or_create first")
        return await self._repository.update_display_name(profile, display_name)

    async def update_preferred_language(self, user_id: UUID, language: str) -> Profile:
        """Aggiorna la lingua di output preferita dell'utente corrente.

        Pre-requisito: il profile esiste (chiamare get_or_create prima) e
        `language` e' gia' validata dallo schema (ProfileUpdate). Sotto RLS:
        l'UPDATE e' permesso SOLO se id == sub_claim.
        """
        profile = await self._repository.get_by_id(user_id)
        if profile is None:
            raise RuntimeError(f"Profile {user_id} not found — call get_or_create first")
        return await self._repository.update_preferred_language(profile, language)

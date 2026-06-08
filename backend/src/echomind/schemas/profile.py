"""Schemas Pydantic per la risorsa Profile.

Convenzione naming (CQS — Command/Query Separation):
- `ProfileRead`   : ciò che l'API RITORNA (output).
- `ProfileUpdate` : ciò che l'API ACCETTA in modifica (input partial).

Mai un singolo schema "Profile" usato per entrambi: input e output hanno
vincoli diversi (es. `id` è sempre nell'output, mai nell'input).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echomind.core.language import SUPPORTED_LANGUAGES


class ProfileRead(BaseModel):
    """Profile come visto dal client (output di GET /profiles/me).

    `from_attributes=True` permette di costruire questo schema direttamente
    da un oggetto SQLAlchemy:

        profile_model = await repository.get_by_id(user_id)
        ProfileRead.model_validate(profile_model)   # legge gli attributi
    """

    id: UUID = Field(description="UUID dell'utente (matcha auth.users.id)")
    display_name: str | None = Field(default=None, description="Nome visualizzato")
    preferred_language: str = Field(
        description="Lingua di output preferita (it/en) per summary, grafo e risposte RAG."
    )
    created_at: datetime = Field(description="Timestamp creazione (UTC)")
    updated_at: datetime = Field(description="Timestamp ultimo aggiornamento (UTC)")

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    """Payload PATCH /profiles/me.

    Tutti i campi sono opzionali: PATCH è un'operazione "partial update".
    Solo i campi presenti nel JSON ricevuto verranno modificati.

    `extra="forbid"` rifiuta campi sconosciuti → previene typo silenziosi
    da parte del client (es. `displayName` invece di `display_name`).
    """

    display_name: str | None = Field(
        default=None,
        max_length=120,
        description="Nuovo nome visualizzato. Set a null per rimuoverlo.",
    )
    preferred_language: str | None = Field(
        default=None,
        description="Lingua di output preferita (it/en). Omessa = invariata.",
    )

    @field_validator("preferred_language")
    @classmethod
    def _validate_language(cls, value: str | None) -> str | None:
        """Accetta solo lingue supportate (case-insensitive); altrimenti 422.

        A differenza di display_name, preferred_language NON puo' essere
        azzerata (colonna NOT NULL): un client che la include deve passare una
        lingua valida. Ometterla del tutto la lascia invariata.
        """
        if value is None:
            return None
        code = value.strip().lower()
        if code not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Lingua non supportata: {value!r}. Ammesse: {', '.join(SUPPORTED_LANGUAGES)}."
            )
        return code

    model_config = ConfigDict(extra="forbid")

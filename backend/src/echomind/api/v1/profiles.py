"""Endpoint /profiles/me — gestione del profilo dell'utente corrente.

- GET    /profiles/me  → ritorna il profile (creandolo lazy se non esiste)
- PATCH  /profiles/me  → aggiorna display_name dell'utente corrente

Pattern: l'endpoint è solo "orchestrazione del flusso HTTP". Tutta la
business logic (just-in-time provisioning, RLS, persistenza) vive nei
layer sotto (service, repository).
"""

from __future__ import annotations

from fastapi import APIRouter

from echomind.api.deps import ProfileServiceDep, UserIdDep
from echomind.schemas.profile import ProfileRead, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get(
    "/me",
    response_model=ProfileRead,
    summary="Ritorna il profile dell'utente corrente",
    description=(
        "Se l'utente è autenticato ma non ha ancora un profile, viene creato "
        "automaticamente (just-in-time provisioning). Restituisce sempre 200."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        403: {"description": "Token valido ma claim obbligatori mancanti"},
    },
)
async def get_my_profile(
    user_id: UserIdDep,
    profile_service: ProfileServiceDep,
) -> ProfileRead:
    """GET /profiles/me — idempotente, crea il profile se assente."""
    profile = await profile_service.get_or_create(user_id)
    return ProfileRead.model_validate(profile)


@router.patch(
    "/me",
    response_model=ProfileRead,
    summary="Aggiorna il profile dell'utente corrente",
    description=(
        "Aggiornamento parziale: solo i campi PRESENTI nel body vengono "
        "modificati. Set `display_name` a `null` per rimuoverlo. "
        "`preferred_language` (it/en) cambia la lingua di output di summary, "
        "grafo e risposte RAG."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        403: {"description": "Token valido ma claim obbligatori mancanti"},
        422: {"description": "Body malformato, lingua non supportata o campi extra"},
    },
)
async def patch_my_profile(
    user_id: UserIdDep,
    payload: ProfileUpdate,
    profile_service: ProfileServiceDep,
) -> ProfileRead:
    """PATCH /profiles/me — aggiorna SOLO i campi effettivamente forniti.

    Usiamo `model_fields_set` per distinguere "campo assente" (lascia invariato)
    da "campo a null" (es. azzera display_name): cosi' un PATCH che cambia solo
    la lingua non cancella il display_name, e viceversa.
    """
    # Garantisce esistenza prima dell'update (just-in-time create se serve)
    await profile_service.get_or_create(user_id)

    provided = payload.model_fields_set
    if "display_name" in provided:
        await profile_service.update_display_name(user_id, payload.display_name)
    if "preferred_language" in provided and payload.preferred_language is not None:
        await profile_service.update_preferred_language(user_id, payload.preferred_language)

    updated = await profile_service.get_or_create(user_id)
    return ProfileRead.model_validate(updated)

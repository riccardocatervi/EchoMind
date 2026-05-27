"""Endpoint /users/me — echo dei claim JWT autenticati.

Questo endpoint NON tocca il DB: serve solo per:
1. Verificare che l'auth pipeline (header → JWT → claims) funzioni
2. Debug rapido per il client ("chi sono?")
3. Test integration di tutti gli exception handler

Per accedere ai dati custom dell'utente (profile DB), useremo /profiles/me.
"""

from __future__ import annotations

from fastapi import APIRouter

from echomind.api.deps import ClaimsDep
from echomind.core.security import JWTClaims

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=JWTClaims,
    summary="Claim del token JWT corrente",
    description=(
        "Ritorna i claim del JWT autenticato (sub, aud, exp, eventuali extra). "
        "Niente accesso DB: utile per debug e per il client per sapere 'chi sono'."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        403: {"description": "Token valido ma claim obbligatori mancanti"},
    },
)
async def get_me(claims: ClaimsDep) -> JWTClaims:
    """Ritorna i claim del JWT corrente, già validati."""
    return claims

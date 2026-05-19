"""Validazione dei JWT firmati da Supabase.

Architettura:

    HTTP request
        ↓ header: Authorization: Bearer <jwt>
    extract_token(headers)                              ← stringa raw
        ↓
    decode_and_validate(token, settings)                ← oggetto JWTClaims
        ↓
    api/deps.get_current_user_id (dipendenza FastAPI)
        ↓
    endpoint handler

Validazioni applicate:
1. Header `Authorization` presente e ben formato (`Bearer <token>`)
2. Firma valida (HMAC-SHA256 con `supabase_jwt_secret`)
3. Non scaduto (`exp` > now)
4. Audience matcha (`aud == settings.supabase_jwt_audience`)
5. Claim obbligatori presenti (`sub`)
6. `sub` è un UUID ben formato

Errori sollevati: classi dedicate (vedi sotto). Verranno mappate a
status code HTTP da api/deps.py.

Sicurezza:
- Algoritmo accettato è PIN-ato (`algorithms=["HS256"]`): previene
  algorithm confusion attacks (token con `alg: "none"`, `alg: "RS256"`, ...).
- `verify_aud=True` esplicito: rifiuta JWT emessi per servizi terzi
  con lo stesso secret.
"""

from __future__ import annotations

from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel, Field, ValidationError

from echomind.core.config import Settings


# -----------------------------------------------------------------------------
# Eccezioni di dominio
# -----------------------------------------------------------------------------
class AuthError(Exception):
    """Base class per tutti gli errori di autenticazione."""


class MissingTokenError(AuthError):
    """Header Authorization assente o malformato."""


class InvalidTokenError(AuthError):
    """Token decodificabile ma firma/struttura non valida."""


class ExpiredTokenError(AuthError):
    """Token scaduto (claim `exp` nel passato)."""


class InvalidAudienceError(AuthError):
    """Claim `aud` non matcha l'audience atteso."""


class MissingClaimError(AuthError):
    """Un claim obbligatorio (es. `sub`) è assente o malformato."""


# -----------------------------------------------------------------------------
# Modello tipato dei claim
# -----------------------------------------------------------------------------
class JWTClaims(BaseModel):
    """Claim del JWT, tipizzati.

    Solo i claim che usiamo davvero sono qui. `model_config` permette extra
    claim (Supabase aggiunge `email`, `phone`, `role`, ecc.) senza farli
    fallire la validazione.
    """

    sub: UUID = Field(description="User ID univoco (UUID v4)")
    aud: str = Field(description="Audience del token (es. 'authenticated')")
    exp: int = Field(description="Scadenza (Unix epoch seconds)")
    iat: int | None = Field(default=None, description="Issued at (Unix epoch)")

    # Permetti claim extra emessi da Supabase senza errori di validazione
    model_config = {"extra": "allow"}


# -----------------------------------------------------------------------------
# Estrazione del token dall'header Authorization
# -----------------------------------------------------------------------------
def extract_bearer_token(authorization_header: str | None) -> str:
    """Estrae il JWT da un header `Authorization: Bearer <token>`.

    Args:
        authorization_header: valore raw del header (può essere None).

    Returns:
        Il token (senza il prefisso 'Bearer ').

    Raises:
        MissingTokenError: se header assente o non in formato Bearer.
    """
    if not authorization_header:
        raise MissingTokenError("Authorization header is missing")

    parts = authorization_header.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise MissingTokenError("Authorization header must be in format 'Bearer <token>'")

    token = parts[1].strip()
    if not token:
        raise MissingTokenError("Bearer token is empty")

    return token


# -----------------------------------------------------------------------------
# Decodifica + validazione
# -----------------------------------------------------------------------------
def decode_and_validate(token: str, settings: Settings) -> JWTClaims:
    """Decodifica il JWT, verifica firma/scadenza/audience, ritorna i claim.

    Args:
        token: stringa JWT raw (senza 'Bearer ').
        settings: configurazione applicativa (contiene secret + audience).

    Returns:
        JWTClaims con `sub`, `aud`, `exp`, eventuali claim extra.

    Raises:
        ExpiredTokenError: token scaduto.
        InvalidAudienceError: `aud` non matcha settings.supabase_jwt_audience.
        InvalidTokenError: firma invalida, JSON malformato, header sbagliato.
        MissingClaimError: claim obbligatori mancanti (es. 'sub').
    """
    try:
        # `algorithms=[...]` PINNATO esplicitamente: previene algorithm confusion.
        # `audience=...`: la libreria verifica che claim `aud` matchi.
        # Se non matcha → JWTClaimsError (sottoclasse di JWTError) → catchato sotto.
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret.get_secret_value(),
            algorithms=[settings.supabase_jwt_algorithm],
            audience=settings.supabase_jwt_audience,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                # `iat` non strettamente obbligatorio per Supabase
                "require_iat": False,
                # `sub` lo verifichiamo via Pydantic dopo
                "require_sub": False,
            },
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError(str(exc)) from exc
    except JWTError as exc:
        # python-jose: gli errori di audience finiscono qui (JWTClaimsError).
        # Distinguiamo per messaggio per dare errore più chiaro all'utente.
        if "audience" in str(exc).lower():
            raise InvalidAudienceError(str(exc)) from exc
        raise InvalidTokenError(str(exc)) from exc

    # Validazione applicativa: trasforma il dict in JWTClaims tipizzato.
    # Se manca `sub` o non è UUID, ValidationError → MissingClaimError.
    try:
        return JWTClaims.model_validate(payload)
    except ValidationError as exc:
        raise MissingClaimError(f"JWT claims validation failed: {exc}") from exc

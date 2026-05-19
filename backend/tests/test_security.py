"""Test della validazione JWT.

Copre OGNI percorso di errore, perché ognuno corrisponde a una verifica
di sicurezza che NON deve mai mancare:

- Token assente / malformato → MissingTokenError
- Firma fasulla → InvalidTokenError
- Algoritmo sbagliato (algorithm confusion) → InvalidTokenError
- Scadenza nel passato → ExpiredTokenError
- Audience sbagliato → InvalidAudienceError
- Claim `sub` mancante o non UUID → MissingClaimError

I JWT di test vengono FIRMATI manualmente con `pyjwt` usando lo stesso
secret della Settings di test. Niente integrazione con Supabase qui.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.core.security import (
    ExpiredTokenError,
    InvalidAudienceError,
    InvalidTokenError,
    JWTClaims,
    MissingClaimError,
    MissingTokenError,
    decode_and_validate,
    extract_bearer_token,
)

# -----------------------------------------------------------------------------
# Fixtures: settings + helper per firmare JWT validi
# -----------------------------------------------------------------------------
TEST_SECRET = "test-secret-with-at-least-64-bytes-for-hs256-and-hs512-attack-tests"
TEST_AUDIENCE = "authenticated"


@pytest.fixture
def settings() -> Settings:
    """Settings con secret e audience deterministici per i test."""
    return Settings.model_construct(
        app_env="development",
        log_level="INFO",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_jwt_secret=SecretStr(TEST_SECRET),
        supabase_jwt_algorithm="HS256",
        supabase_jwt_audience=TEST_AUDIENCE,
    )


def _make_jwt(
    *,
    sub: str | None = None,
    aud: str = TEST_AUDIENCE,
    exp_offset_seconds: int = 3600,
    algorithm: str = "HS256",
    secret: str = TEST_SECRET,
    extra_claims: dict[str, object] | None = None,
) -> str:
    """Firma un JWT custom per i test.

    Permette override di tutti i parametri per testare ogni percorso di errore.
    """
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_offset_seconds)).timestamp()),
    }
    if sub is not None:
        payload["sub"] = sub
    if extra_claims:
        payload.update(extra_claims)
    return pyjwt.encode(payload, secret, algorithm=algorithm)


# =============================================================================
# extract_bearer_token
# =============================================================================
class TestExtractBearerToken:
    def test_extracts_valid_bearer(self) -> None:
        assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_case_insensitive_scheme(self) -> None:
        assert extract_bearer_token("bearer xyz") == "xyz"
        assert extract_bearer_token("BEARER xyz") == "xyz"

    def test_none_header_raises(self) -> None:
        with pytest.raises(MissingTokenError, match="missing"):
            extract_bearer_token(None)

    def test_empty_header_raises(self) -> None:
        with pytest.raises(MissingTokenError):
            extract_bearer_token("")

    def test_wrong_scheme_raises(self) -> None:
        with pytest.raises(MissingTokenError, match="Bearer"):
            extract_bearer_token("Basic abc")

    def test_no_token_after_bearer_raises(self) -> None:
        with pytest.raises(MissingTokenError):
            extract_bearer_token("Bearer ")

    def test_only_scheme_raises(self) -> None:
        with pytest.raises(MissingTokenError):
            extract_bearer_token("Bearer")


# =============================================================================
# decode_and_validate — happy path
# =============================================================================
class TestDecodeAndValidateHappyPath:
    def test_valid_token_returns_claims(self, settings: Settings) -> None:
        sub = str(uuid4())
        token = _make_jwt(sub=sub)
        claims = decode_and_validate(token, settings)

        assert isinstance(claims, JWTClaims)
        assert claims.sub == UUID(sub)
        assert claims.aud == TEST_AUDIENCE
        assert claims.exp > int(datetime.now(UTC).timestamp())

    def test_extra_claims_preserved(self, settings: Settings) -> None:
        """Claim aggiuntivi (email, role) sono accettati e accessibili."""
        token = _make_jwt(
            sub=str(uuid4()),
            extra_claims={"email": "alice@example.com", "role": "authenticated"},
        )
        claims = decode_and_validate(token, settings)
        # I claim extra sono nel model_dump (extra="allow")
        dumped = claims.model_dump()
        assert dumped["email"] == "alice@example.com"
        assert dumped["role"] == "authenticated"


# =============================================================================
# decode_and_validate — error paths (uno per ogni eccezione)
# =============================================================================
class TestDecodeAndValidateErrors:
    def test_expired_token(self, settings: Settings) -> None:
        token = _make_jwt(sub=str(uuid4()), exp_offset_seconds=-60)
        with pytest.raises(ExpiredTokenError):
            decode_and_validate(token, settings)

    def test_invalid_signature(self, settings: Settings) -> None:
        # Secret abbastanza lungo per non triggerare InsecureKeyLengthWarning,
        # ma DIVERSO da quello in settings → firma non matcha → InvalidTokenError.
        wrong_secret = "wrong-secret-but-equally-long-64-bytes-to-avoid-warning-xxxxxxx"
        token = _make_jwt(sub=str(uuid4()), secret=wrong_secret)
        with pytest.raises(InvalidTokenError):
            decode_and_validate(token, settings)

    def test_wrong_audience(self, settings: Settings) -> None:
        token = _make_jwt(sub=str(uuid4()), aud="some-other-service")
        with pytest.raises(InvalidAudienceError):
            decode_and_validate(token, settings)

    def test_missing_sub_claim(self, settings: Settings) -> None:
        """Senza `sub`, MissingClaimError (validazione Pydantic)."""
        token = _make_jwt(sub=None)
        with pytest.raises(MissingClaimError):
            decode_and_validate(token, settings)

    def test_sub_is_not_uuid(self, settings: Settings) -> None:
        token = _make_jwt(sub="not-a-uuid")
        with pytest.raises(MissingClaimError):
            decode_and_validate(token, settings)

    def test_garbage_token(self, settings: Settings) -> None:
        with pytest.raises(InvalidTokenError):
            decode_and_validate("this.is.garbage", settings)

    def test_wrong_algorithm_attack(self, settings: Settings) -> None:
        """Algorithm confusion: token firmato con HS512 invece di HS256.

        Anche se HS512 usa lo stesso secret HMAC, NON deve essere accettato
        perché `algorithms=["HS256"]` è pinnato.
        """
        token = _make_jwt(sub=str(uuid4()), algorithm="HS512")
        with pytest.raises(InvalidTokenError):
            decode_and_validate(token, settings)

    def test_none_algorithm_attack(self, settings: Settings) -> None:
        """Token unsigned (`alg: "none"`): deve essere rifiutato categoricamente."""
        token = pyjwt.encode(
            {"sub": str(uuid4()), "aud": TEST_AUDIENCE, "exp": 9999999999},
            key="",
            algorithm="none",
        )
        with pytest.raises(InvalidTokenError):
            decode_and_validate(token, settings)

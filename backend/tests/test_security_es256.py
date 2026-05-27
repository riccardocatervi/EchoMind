"""Test ES256: validation di JWT firmati con ECDSA P-256.

Generiamo una coppia di chiavi ECC P-256 ad-hoc (privata per firmare, pubblica
per verificare) → emettiamo un JWT con la privata → settiamo nella `Settings`
la pubblica → la validazione passa.

Replica esattamente il pattern Supabase ES256, ma con chiavi locali. Niente
dipendenza dalla rete o da Supabase reale.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt as jose_jwt
from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.core.security import (
    InvalidTokenError,
    decode_and_validate,
)


def _generate_p256_keypair() -> tuple[str, str]:
    """Genera coppia (private_pem, public_pem) ECC P-256."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def _public_pem_to_jwk_json(public_pem: str) -> str:
    """Converte PEM in JWK (JSON Web Key) come stringa JSON.

    Replica il formato che Supabase ci mostra nella sua dashboard.
    """
    import base64
    import json

    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    public_key = load_pem_public_key(public_pem.encode("utf-8"))
    assert isinstance(public_key, ec.EllipticCurvePublicKey)
    nums = public_key.public_numbers()
    # Coordinate x e y in base64-url senza padding (RFC 7518 Sec 6.2.1)
    x_bytes = nums.x.to_bytes(32, "big")
    y_bytes = nums.y.to_bytes(32, "big")
    x_b64 = base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode("ascii")
    y_b64 = base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode("ascii")
    return json.dumps(
        {
            "kty": "EC",
            "crv": "P-256",
            "alg": "ES256",
            "x": x_b64,
            "y": y_b64,
            "key_ops": ["verify"],
        }
    )


@pytest.fixture
def es256_keypair() -> tuple[str, str]:
    return _generate_p256_keypair()


@pytest.fixture
def es256_settings(es256_keypair: tuple[str, str]) -> Settings:
    _, public_pem = es256_keypair
    return Settings.model_construct(
        app_env="development",
        log_level="WARNING",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_jwt_algorithm="ES256",
        supabase_jwt_secret=None,
        supabase_jwt_public_key=SecretStr(public_pem),
        supabase_jwt_audience="authenticated",
    )


def _sign_es256(payload: dict[str, object], private_pem: str) -> str:
    """Firma payload con chiave privata P-256, algoritmo ES256."""
    # python-jose usa "ES256" come nome standard per ECDSA P-256 + SHA-256
    return jose_jwt.encode(payload, private_pem, algorithm="ES256")


def test_es256_happy_path(es256_keypair: tuple[str, str], es256_settings: Settings) -> None:
    """JWT firmato con privata P-256 → validato con pubblica → OK."""
    private_pem, _ = es256_keypair
    sub = str(uuid4())
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": sub,
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }

    token = _sign_es256(payload, private_pem)
    claims = decode_and_validate(token, es256_settings)

    assert str(claims.sub) == sub
    assert claims.aud == "authenticated"


def test_es256_rejects_token_signed_with_different_key(
    es256_settings: Settings,
) -> None:
    """Token firmato con un'ALTRA chiave privata P-256 → rifiutato.

    Prova concreta che la verifica asimmetrica funziona: solo chi possiede
    LA chiave privata corretta può forgiare token validi per noi.
    """
    other_private, _ = _generate_p256_keypair()
    sub = str(uuid4())
    now = datetime.now(UTC)
    token = _sign_es256(
        {
            "sub": sub,
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        other_private,
    )

    with pytest.raises(InvalidTokenError):
        decode_and_validate(token, es256_settings)


def test_es256_works_with_jwk_json_format(es256_keypair: tuple[str, str]) -> None:
    """La chiave pubblica può essere fornita anche come JSON JWK, non solo PEM.

    Questo è il formato che Supabase usa nella sua dashboard. python-jose
    supporta entrambi nativamente.
    """
    private_pem, public_pem = es256_keypair
    jwk_json = _public_pem_to_jwk_json(public_pem)

    settings = Settings.model_construct(
        app_env="development",
        log_level="WARNING",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_jwt_algorithm="ES256",
        supabase_jwt_secret=None,
        supabase_jwt_public_key=SecretStr(jwk_json),
        supabase_jwt_audience="authenticated",
    )

    sub = str(uuid4())
    now = datetime.now(UTC)
    token = _sign_es256(
        {
            "sub": sub,
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        private_pem,
    )

    claims = decode_and_validate(token, settings)
    assert str(claims.sub) == sub


def test_settings_rejects_es256_without_public_key() -> None:
    """`Settings` deve fallire se algorithm=ES256 ma public_key è None."""
    with pytest.raises(ValueError, match="supabase_jwt_public_key"):
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            app_env="development",
            log_level="INFO",
            database_url="postgresql+asyncpg://u:p@localhost/db",  # type: ignore[arg-type]
            supabase_jwt_algorithm="ES256",
            supabase_jwt_secret=None,
            supabase_jwt_public_key=None,
        )


def test_settings_rejects_hs256_without_secret() -> None:
    """`Settings` deve fallire se algorithm=HS256 ma secret è None."""
    with pytest.raises(ValueError, match="supabase_jwt_secret"):
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            app_env="development",
            log_level="INFO",
            database_url="postgresql+asyncpg://u:p@localhost/db",  # type: ignore[arg-type]
            supabase_jwt_algorithm="HS256",
            supabase_jwt_secret=None,
            supabase_jwt_public_key=None,
        )

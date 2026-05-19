"""Test integration di GET /api/v1/users/me — autenticazione completa.

Copre l'intera pipeline:
  request HTTP → middleware → header → JWT decode → claim → endpoint

Casi testati:
- 200: token valido → claim ritornati
- 401: nessun header Authorization
- 401: header malformato (non "Bearer ...")
- 401: token con firma non valida
- 401: token scaduto
- 401: audience sbagliato
- 403: claim `sub` mancante (token valido ma incompleto)

Verifica anche envelope ErrorResponse e header WWW-Authenticate.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest

ENDPOINT = "/api/v1/users/me"


# -----------------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_authenticated_request_returns_claims(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
) -> None:
    """Con un JWT valido, /users/me ritorna i claim."""
    user_id = uuid4()
    response = await client.get(ENDPOINT, headers=auth_headers(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["sub"] == str(user_id)
    assert payload["aud"] == "authenticated"
    assert "exp" in payload


# -----------------------------------------------------------------------------
# 401: token mancante / malformato
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_authorization_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(ENDPOINT)
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"
    # RFC 7235: la 401 DEVE includere WWW-Authenticate
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_malformed_authorization_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Header senza 'Bearer ' davanti → 401 missing_token."""
    response = await client.get(ENDPOINT, headers={"Authorization": "some-token"})
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


@pytest.mark.asyncio
async def test_basic_auth_returns_401(client: httpx.AsyncClient) -> None:
    """Autenticazione con schema diverso da Bearer → 401."""
    response = await client.get(ENDPOINT, headers={"Authorization": "Basic abc==="})
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


# -----------------------------------------------------------------------------
# 401: token invalido (firma, formato, audience)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_garbage_token_returns_401_invalid(client: httpx.AsyncClient) -> None:
    response = await client.get(ENDPOINT, headers={"Authorization": "Bearer this.is.garbage"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_wrong_signature_returns_401_invalid(
    client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
) -> None:
    wrong_secret = "wrong-secret-but-equally-long-64-bytes-to-avoid-warning-xxxxxxx"
    token = make_jwt(sub=str(uuid4()), secret=wrong_secret)
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_wrong_audience_returns_401_audience(
    client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
) -> None:
    token = make_jwt(sub=str(uuid4()), aud="some-other-service")
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_audience"


@pytest.mark.asyncio
async def test_expired_token_returns_401_expired(
    client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
) -> None:
    token = make_jwt(sub=str(uuid4()), exp_offset_seconds=-60)
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "expired_token"


# -----------------------------------------------------------------------------
# 403: token valido ma claim mancanti
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_sub_claim_returns_403(
    client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
) -> None:
    """Token firmato e non scaduto, ma senza `sub` → 403 (validazione applicativa)."""
    token = make_jwt(sub=None)
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["code"] == "missing_claim"


@pytest.mark.asyncio
async def test_sub_not_uuid_returns_403(
    client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
) -> None:
    """Claim sub presente ma non UUID → fail validazione Pydantic → 403."""
    token = make_jwt(sub="not-a-uuid")
    response = await client.get(ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["code"] == "missing_claim"

"""Test integration di /api/v1/profiles/me (GET + PATCH).

Richiede DB locale up (`make dev` + `make migrate`).
Verifica:
- GET crea il profile just-in-time se non esiste
- GET successivi sono idempotenti (stesso profile)
- PATCH aggiorna display_name
- PATCH rifiuta campi extra (extra='forbid')
- Senza auth → 401
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GET_ENDPOINT = "/api/v1/profiles/me"


@pytest.mark.asyncio
async def test_get_creates_profile_just_in_time(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Prima GET crea il profile automaticamente, ritorna 200."""
    user_id = uuid4()
    await seed_auth_user(user_id)

    response = await client.get(GET_ENDPOINT, headers=auth_headers(user_id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["display_name"] is None
    assert "created_at" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_get_is_idempotent(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Chiamate ripetute ritornano lo stesso profile (no duplicati)."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    first = await client.get(GET_ENDPOINT, headers=headers)
    second = await client.get(GET_ENDPOINT, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["created_at"] == second.json()["created_at"]


@pytest.mark.asyncio
async def test_patch_updates_display_name(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """PATCH /profiles/me aggiorna display_name."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    response = await client.patch(GET_ENDPOINT, headers=headers, json={"display_name": "Alice"})

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_patch_can_clear_display_name(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """display_name=null rimuove il nome."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    # 1. Set a name
    await client.patch(GET_ENDPOINT, headers=headers, json={"display_name": "Alice"})
    # 2. Clear it
    response = await client.patch(GET_ENDPOINT, headers=headers, json={"display_name": None})

    assert response.status_code == 200
    assert response.json()["display_name"] is None


@pytest.mark.asyncio
async def test_get_returns_default_language(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Il profile appena creato ha preferred_language='it' (default migration)."""
    user_id = uuid4()
    await seed_auth_user(user_id)

    response = await client.get(GET_ENDPOINT, headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["preferred_language"] == "it"


@pytest.mark.asyncio
async def test_patch_updates_preferred_language(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """PATCH preferred_language='en' cambia la lingua di output."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    response = await client.patch(GET_ENDPOINT, headers=headers, json={"preferred_language": "en"})

    assert response.status_code == 200
    assert response.json()["preferred_language"] == "en"


@pytest.mark.asyncio
async def test_patch_language_preserves_display_name(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Cambiare SOLO la lingua non azzera il display_name (partial update)."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    await client.patch(GET_ENDPOINT, headers=headers, json={"display_name": "Alice"})
    response = await client.patch(GET_ENDPOINT, headers=headers, json={"preferred_language": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["preferred_language"] == "en"
    assert body["display_name"] == "Alice"  # NON cancellato


@pytest.mark.asyncio
async def test_patch_rejects_unsupported_language(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Una lingua non supportata (es. 'fr') -> 422."""
    user_id = uuid4()
    await seed_auth_user(user_id)

    response = await client.patch(
        GET_ENDPOINT,
        headers=auth_headers(user_id),
        json={"preferred_language": "fr"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_extra_fields(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """`extra='forbid'` su ProfileUpdate → 422 su typo del client."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    headers = auth_headers(user_id)

    response = await client.patch(
        GET_ENDPOINT,
        headers=headers,
        json={"displayName": "Alice"},  # typo: camelCase invece di snake_case
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_validates_length(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """display_name oltre 120 char → 422."""
    user_id = uuid4()
    await seed_auth_user(user_id)

    too_long = "x" * 121
    response = await client.patch(
        GET_ENDPOINT,
        headers=auth_headers(user_id),
        json={"display_name": too_long},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_no_auth_returns_401(client: httpx.AsyncClient) -> None:
    """Endpoint protetto: senza token → 401."""
    response = await client.get(GET_ENDPOINT)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_auto_provisions_unseeded_user_in_dev(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    system_session: AsyncSession,
) -> None:
    """In development un utente NON presente in auth.users viene creato in
    automatico (seam Supabase cloud vs Postgres locale): la GET ritorna 200
    invece di 500 sulla FK profiles -> auth.users.

    test_settings ha app_env='development', quindi l'auto-seed e' attivo.
    """
    user_id = uuid4()  # volutamente NON seedato in auth.users
    try:
        response = await client.get(GET_ENDPOINT, headers=auth_headers(user_id))
        assert response.status_code == 200, response.text
        assert response.json()["id"] == str(user_id)
    finally:
        # Cleanup mirato (niente TRUNCATE): rimuove solo l'utente del test.
        await system_session.execute(
            text("DELETE FROM auth.users WHERE id = :id"), {"id": str(user_id)}
        )
        await system_session.commit()

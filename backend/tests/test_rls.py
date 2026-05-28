"""Test RLS isolation — il test PIÙ IMPORTANTE di M1.

Verifica che un utente NON possa MAI vedere o modificare i dati di un altro,
nemmeno se proverà a forzare la richiesta.

Approccio:
1. Crea 2 utenti distinti (Alice e Bob) con profile distinti
2. Alice fa GET /profiles/me con JWT di Alice → vede SOLO i propri dati
3. Bob fa GET /profiles/me con JWT di Bob → vede SOLO i propri dati
4. Alice modifica il proprio display_name → Bob NON è influenzato
5. Verifica diretta nel DB (con bypass RLS) che le righe sono distinte

Questo è il test che giustifica TUTTO il pattern RLS. Senza, qualunque bug
applicativo in futuro (un WHERE dimenticato in una query, un endpoint con
filtro errato, ecc.) potrebbe esporre dati di altri utenti — qui invece
PostgreSQL si oppone in modo categorico.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ENDPOINT = "/api/v1/profiles/me"


@pytest.mark.asyncio
async def test_alice_cannot_see_bobs_profile(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Alice GET /profiles/me ritorna solo Alice, mai Bob."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    # Crea entrambi i profile (just-in-time provisioning)
    await client.get(ENDPOINT, headers=auth_headers(alice_id))
    await client.get(ENDPOINT, headers=auth_headers(bob_id))

    # Alice rivede il proprio
    response = await client.get(ENDPOINT, headers=auth_headers(alice_id))
    assert response.status_code == 200
    assert response.json()["id"] == str(alice_id)
    assert response.json()["id"] != str(bob_id)


@pytest.mark.asyncio
async def test_two_users_have_independent_profiles(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Update di Alice non tocca i dati di Bob."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    # Alice setta il suo nome
    await client.patch(
        ENDPOINT,
        headers=auth_headers(alice_id),
        json={"display_name": "Alice"},
    )
    # Bob setta il suo nome
    await client.patch(
        ENDPOINT,
        headers=auth_headers(bob_id),
        json={"display_name": "Bob"},
    )

    # Bob legge → vede SOLO Bob
    bob_response = await client.get(ENDPOINT, headers=auth_headers(bob_id))
    assert bob_response.json()["display_name"] == "Bob"

    # Alice legge → vede SOLO Alice
    alice_response = await client.get(ENDPOINT, headers=auth_headers(alice_id))
    assert alice_response.json()["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_db_has_both_profiles_distinct(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """Verifica al livello DB (bypassando RLS come superuser): 2 righe distinte.

    Questo prova che i profile esistono fisicamente, ma sono nascosti a
    ciascun utente in via reciproca grazie alle policy RLS.
    """
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    # Crea entrambi i profile
    await client.get(ENDPOINT, headers=auth_headers(alice_id))
    await client.get(ENDPOINT, headers=auth_headers(bob_id))

    # Verifica diretta nel DB (system_session = superuser, bypassa RLS)
    result = await system_session.execute(
        text("SELECT COUNT(*) FROM public.profiles WHERE id IN (:a, :b)"),
        {"a": str(alice_id), "b": str(bob_id)},
    )
    count = result.scalar_one()
    assert count == 2  # 2 profile distinti fisicamente nel DB


@pytest.mark.asyncio
async def test_rls_blocks_select_without_claim(
    client: httpx.AsyncClient,
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """Una sessione `app_runtime` senza claim NON vede nessun profile.

    Test al livello DB: simula esattamente cosa farebbe un attaccante che
    riuscisse a bypassare il livello applicativo (es. SQL injection
    in altre tabelle) e provasse a leggere `profiles`.
    """
    # Seed: 1 utente con profile (via path normale)
    user_id = uuid4()
    await seed_auth_user(user_id)
    # Crea il profile come superuser (simula stato iniziale)
    await system_session.execute(
        text("INSERT INTO public.profiles (id, display_name) VALUES (:id, 'test')"),
        {"id": str(user_id)},
    )
    await system_session.commit()

    # Apri una sessione "app_runtime" SENZA settare il claim sub.
    # Pattern: BEGIN → SET LOCAL ROLE → SELECT (senza set_config) → COMMIT
    await system_session.execute(text("BEGIN"))
    await system_session.execute(text("SET LOCAL ROLE app_runtime"))
    # NON settiamo request.jwt.claim.sub → policy USING ritorna NULL/false
    result = await system_session.execute(text("SELECT COUNT(*) FROM public.profiles"))
    count_without_claim = result.scalar_one()
    await system_session.execute(text("COMMIT"))

    assert count_without_claim == 0  # RLS blocca tutto senza claim


@pytest.mark.asyncio
async def test_rls_blocks_select_with_other_user_claim(
    client: httpx.AsyncClient,
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """Settando un claim diverso dal proprio user_id → 0 righe visibili."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)
    # Crea solo il profile di Alice
    await system_session.execute(
        text("INSERT INTO public.profiles (id, display_name) VALUES (:id, 'Alice')"),
        {"id": str(alice_id)},
    )
    await system_session.commit()

    # Bob prova a vedere il DB con il SUO claim → niente (non ha profile)
    await system_session.execute(text("BEGIN"))
    await system_session.execute(text("SET LOCAL ROLE app_runtime"))
    await system_session.execute(
        text("SELECT set_config('request.jwt.claim.sub', :uid, true)"),
        {"uid": str(bob_id)},
    )
    result = await system_session.execute(text("SELECT COUNT(*) FROM public.profiles"))
    count_for_bob = result.scalar_one()
    await system_session.execute(text("COMMIT"))

    assert count_for_bob == 0  # Bob NON vede il profile di Alice


# =============================================================================
# RLS su documents (M2)
# =============================================================================
@pytest.mark.asyncio
async def test_alice_cannot_see_bobs_documents(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    s3_mock_storage: object,
) -> None:
    """Pattern identico a profiles ma per documents:
    Alice carica i suoi documenti, Bob carica i suoi → GET /documents
    di ciascuno ritorna solo quello dell'altro 'invisibile'.
    """
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    alice_headers = auth_headers(alice_id)
    bob_headers = auth_headers(bob_id)

    # Alice crea 2 documenti, Bob ne crea 1
    for i in range(2):
        await client.post(
            "/api/v1/documents",
            headers=alice_headers,
            json={
                "filename": f"alice-{i}.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 100,
            },
        )
    await client.post(
        "/api/v1/documents",
        headers=bob_headers,
        json={
            "filename": "bob.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
    )

    # Alice vede 2; Bob vede 1
    alice_list = await client.get("/api/v1/documents", headers=alice_headers)
    bob_list = await client.get("/api/v1/documents", headers=bob_headers)
    assert len(alice_list.json()) == 2
    assert len(bob_list.json()) == 1
    # Nessun documento di Alice ha owner_id = bob_id
    assert all(d["owner_id"] == str(alice_id) for d in alice_list.json())
    assert all(d["owner_id"] == str(bob_id) for d in bob_list.json())


@pytest.mark.asyncio
async def test_alice_cannot_get_bobs_document_by_id(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    s3_mock_storage: object,
) -> None:
    """Even with the right URL, Alice gets 404 for Bob's document."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    # Bob crea documento
    bob_init = await client.post(
        "/api/v1/documents",
        headers=auth_headers(bob_id),
        json={
            "filename": "secret.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    bob_doc_id = bob_init.json()["document_id"]

    # Alice tenta GET dell'id di Bob → 404 (RLS lo nasconde)
    response = await client.get(f"/api/v1/documents/{bob_doc_id}", headers=auth_headers(alice_id))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alice_cannot_delete_bobs_document(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    s3_mock_storage: object,
    system_session: AsyncSession,
) -> None:
    """DELETE su documento altrui → 404 (RLS rende l'id 'invisibile')."""
    alice_id = uuid4()
    bob_id = uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)

    bob_init = await client.post(
        "/api/v1/documents",
        headers=auth_headers(bob_id),
        json={
            "filename": "important.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    bob_doc_id = bob_init.json()["document_id"]

    # Alice tenta delete → 404
    response = await client.delete(
        f"/api/v1/documents/{bob_doc_id}", headers=auth_headers(alice_id)
    )
    assert response.status_code == 404

    # Verifica al DB (system session): documento di Bob ancora presente
    result = await system_session.execute(
        text("SELECT COUNT(*) FROM public.documents WHERE id = :id"),
        {"id": bob_doc_id},
    )
    assert result.scalar_one() == 1

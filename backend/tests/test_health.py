"""Test integration di GET /api/v1/health.

Verifica:
- 200 OK
- Schema risposta corretto
- Header X-Request-ID presente (middleware funzionante)
- L'app è raggiungibile via AsyncClient (smoke complessivo dell'app factory)
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    """Smoke: l'endpoint /health risponde 200 con il payload atteso."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "development"
    assert isinstance(payload["version"], str)
    assert len(payload["version"]) > 0


@pytest.mark.asyncio
async def test_health_sets_request_id_header(client: httpx.AsyncClient) -> None:
    """Il middleware RequestIdMiddleware deve aggiungere X-Request-ID."""
    response = await client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    # Generato come UUID → 36 char con trattini
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36
    assert request_id.count("-") == 4


@pytest.mark.asyncio
async def test_health_respects_inbound_request_id(client: httpx.AsyncClient) -> None:
    """Se il client manda X-Request-ID, lo riusiamo (utile per trace).

    Pattern fondamentale per debugging in produzione e per integrazione
    con sistemi di tracing distribuito.
    """
    given = "req-from-client-1234"
    response = await client.get("/api/v1/health", headers={"X-Request-ID": given})
    assert response.headers["x-request-id"] == given


@pytest.mark.asyncio
async def test_health_does_not_require_auth(client: httpx.AsyncClient) -> None:
    """Health è pubblico — niente Authorization → comunque 200."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

"""Test del CORSMiddleware (abilitatore frontend, M6).

La SPA React vive su un origin diverso (es. http://localhost:5173) dall'API:
senza CORS il browser blocca ogni fetch e il preflight OPTIONS dell'upload.
Verifichiamo che il middleware:
- risponda al preflight OPTIONS di un'origine AMMESSA con gli header CORS (200);
- NON conceda l'header Access-Control-Allow-Origin a un'origine NON ammessa;
- aggiunga l'header anche a una risposta reale (qui un 401), perche' CORS e' il
  middleware piu' esterno e avvolge anche le risposte d'errore.

L'origine ammessa nei test e' il default di Settings: http://localhost:5173
(le test_settings non sovrascrivono CORS_ALLOW_ORIGINS).
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.asyncio

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "http://evil.example"


async def test_preflight_allowed_origin(client: httpx.AsyncClient) -> None:
    """OPTIONS preflight da origine ammessa --> 200 + header CORS."""
    response = await client.options(
        "/api/v1/documents",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_preflight_disallowed_origin(client: httpx.AsyncClient) -> None:
    """OPTIONS preflight da origine NON ammessa --> nessun header di concessione."""
    response = await client.options(
        "/api/v1/documents",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette risponde "Disallowed CORS origin" e NON include l'header ACAO:
    # il browser blocchera' la richiesta lato client.
    assert "access-control-allow-origin" not in response.headers


async def test_actual_request_gets_cors_header_even_on_error(
    client: httpx.AsyncClient,
) -> None:
    """Richiesta reale (non preflight) senza auth: 401 ma con header CORS.

    Prova che CORS e' piu' esterno degli exception handler: anche un errore
    riceve Access-Control-Allow-Origin, altrimenti il browser non mostrerebbe
    nemmeno il messaggio d'errore al codice JS.
    """
    response = await client.get("/api/v1/documents", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

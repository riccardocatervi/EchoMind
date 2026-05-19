"""Endpoint /health — liveness check.

Convenzione:
- 200 = applicazione viva e in grado di rispondere a HTTP
- NO controllo DB qui: confonderebbe "DB down" con "app down"
  (per quello useremo /readiness in M9, distinto)

Questo endpoint deve:
- Essere veloce (<10ms)
- Non richiedere autenticazione
- Non fare query DB
- Essere chiamabile centinaia di volte al secondo da load balancer
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from echomind.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Ritorna 200 se l'app risponde. Non controlla DB/dipendenze.",
)
async def get_health(request: Request) -> HealthResponse:
    """Liveness check.

    `request.app.state.settings` viene popolato nel lifespan di main.py.
    """
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version=request.app.version,
        environment=settings.app_env,
    )

"""Schemas Pydantic condivisi (response generiche, error envelope, ...)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Risposta dell'endpoint /health.

    Niente claim sensibili, niente DB query: deve restare ultra-leggero
    perché viene chiamato continuamente da load balancer e monitoring.
    """

    status: Literal["ok"] = Field(default="ok", description="Sempre 'ok' se l'app risponde")
    version: str = Field(description="Versione applicativa (semver)")
    environment: str = Field(description="Ambiente di esecuzione: development/staging/production")


class ErrorResponse(BaseModel):
    """Envelope standard per errori HTTP.

    Usato dai handler delle eccezioni di dominio per dare al client
    un formato di errore prevedibile e tipizzato.
    """

    detail: str = Field(description="Messaggio leggibile dall'utente")
    code: str | None = Field(default=None, description="Codice errore machine-readable")

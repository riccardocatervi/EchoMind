"""Application configuration.

Pattern: tipizziamo TUTTA la configurazione con Pydantic Settings.
Vantaggi rispetto a `os.environ.get(...)` sparso nel codice:

- Validazione all'avvio: se .env è malformato, l'app NON parte (fail fast).
- Tipi forti: l'IDE conosce la struttura, mypy verifica i tipi.
- Secrets-aware: SecretStr non leakka i valori nei log/repr.
- Singleton: `get_settings()` è cachato → un solo oggetto in tutta l'app.

Riferimento: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tutte le variabili d'ambiente dell'applicazione, in un solo posto.

    Le variabili vengono lette in quest'ordine di priorità (Pydantic default):
      1. argomenti passati al costruttore (es. nei test: `Settings(database_url=...)`)
      2. variabili d'ambiente del processo
      3. file `.env` nella directory di lavoro
      4. default dichiarati qui sotto

    `case_sensitive=False` significa che `DATABASE_URL` e `database_url`
    sono trattati come la stessa variabile.
    """

    # -------------------------------------------------------------------------
    # Ambiente applicativo
    # -------------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Ambiente di esecuzione: influenza logging, error pages, ecc.",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Soglia minima dei log emessi.",
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: PostgresDsn = Field(
        ...,  # obbligatorio: niente default → app non parte se manca
        description=(
            "Connection string PostgreSQL. Formato: postgresql+asyncpg://user:pass@host:port/dbname"
        ),
    )

    # -------------------------------------------------------------------------
    # Supabase JWT (autenticazione)
    # -------------------------------------------------------------------------
    supabase_jwt_secret: SecretStr = Field(
        ...,
        description=(
            "Secret HS256 per validare i JWT firmati da Supabase. "
            "Ottenuto da: Supabase Dashboard → Settings → API → JWT Secret."
        ),
    )

    supabase_jwt_algorithm: Literal["HS256"] = Field(
        default="HS256",
        description=(
            "Algoritmo di firma. Supabase usa HS256 di default. "
            "Pin esplicito per prevenire 'algorithm confusion attacks'."
        ),
    )

    supabase_jwt_audience: str = Field(
        default="authenticated",
        description=(
            "Claim 'aud' atteso nei JWT. Supabase emette token con "
            "aud='authenticated' per utenti loggati."
        ),
    )

    # -------------------------------------------------------------------------
    # Configurazione del loader Pydantic
    # -------------------------------------------------------------------------
    # `env_file=("../.env", ".env")` cerca .env prima nel parent (root del repo,
    # dove vive il vero file) poi nella cwd del processo (utile in test).
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignora variabili extra in .env (es. NEO4J_*, B2_*: arrivano in M2+)
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ritorna l'istanza singleton di Settings.

    Pattern singleton via `lru_cache`: la prima chiamata costruisce
    l'oggetto (parsing .env, validazione); le successive ritornano lo
    stesso oggetto cached. Costo O(1) dopo la prima chiamata.

    Nei test, per forzare il reload (es. con env diverso):
        from echomind.core.config import get_settings
        get_settings.cache_clear()
    """
    return Settings()  # type: ignore[call-arg]
    # ↑ mypy ignore: Settings() costruisce dai env vars, ma mypy vorrebbe
    # tutti i campi obbligatori passati esplicitamente. Comportamento atteso.

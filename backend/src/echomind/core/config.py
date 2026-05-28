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
from typing import Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, model_validator
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
        ...,  # obbligatorio: niente default --> app non parte se manca
        description=(
            "Connection string PostgreSQL. Formato: postgresql+asyncpg://user:pass@host:port/dbname"
        ),
    )

    # -------------------------------------------------------------------------
    # Supabase JWT (autenticazione)
    # -------------------------------------------------------------------------
    # Supabase supporta due algoritmi:
    #   - HS256 (legacy, simmetrico): un secret condiviso firma e verifica.
    #     Usato dai progetti vecchi e dai nostri test (per semplicità di firma).
    #   - ES256 (corrente, asimmetrico): chiave privata su Supabase, pubblica
    #     (ECDSA P-256, formato PEM) distribuita per la verifica.
    # In dev/test possiamo usare HS256. In produzione: ES256 (default Supabase).
    supabase_jwt_algorithm: Literal["HS256", "ES256"] = Field(
        default="HS256",
        description=(
            "Algoritmo di firma JWT. HS256 (legacy) o ES256 (corrente Supabase). "
            "Pin esplicito per prevenire algorithm confusion attacks."
        ),
    )

    supabase_jwt_secret: SecretStr | None = Field(
        default=None,
        description=(
            "Secret HMAC per HS256. Obbligatorio se algorithm=HS256, ignorato altrimenti. "
            "Source (HS256 legacy): Supabase Dashboard → JWT Keys → Legacy HS256."
        ),
    )

    supabase_jwt_public_key: SecretStr | None = Field(
        default=None,
        description=(
            "Chiave pubblica ECDSA P-256 in formato PEM per ES256. "
            "Obbligatoria se algorithm=ES256. "
            "Source: Supabase Dashboard → JWT Keys → Current Key → Public Key (PEM). "
            "Inserire come stringa singola con newline letterali (\\n)."
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
    # Backblaze B2 (S3-compatible object storage) — M2
    # -------------------------------------------------------------------------
    # Tutti opzionali in dev (usiamo moto come mock S3 nei test).
    # Obbligatori in produzione: garantito dal validator cross-field sotto.
    b2_key_id: SecretStr | None = Field(
        default=None,
        description=(
            "Backblaze B2 keyID. Source: secure.backblaze.com → App Keys. "
            "Obbligatorio se app_env=production."
        ),
    )

    b2_application_key: SecretStr | None = Field(
        default=None,
        description=("Backblaze B2 applicationKey (secret). Obbligatorio se app_env=production."),
    )

    b2_bucket_name: str | None = Field(
        default=None,
        description="Nome del bucket B2 privato. Obbligatorio se app_env=production.",
    )

    b2_endpoint: str | None = Field(
        default=None,
        description=(
            "URL endpoint S3-compatible di B2, es. "
            "https://s3.eu-central-003.backblazeb2.com. "
            "Obbligatorio se app_env=production."
        ),
    )

    b2_region: str = Field(
        default="eu-central-003",
        description="Region B2 (parte del path nell'endpoint). Default EU central.",
    )

    # -------------------------------------------------------------------------
    # Upload limits — M2
    # -------------------------------------------------------------------------
    max_upload_size_bytes: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        gt=0,
        description=(
            "Limite massimo per file in bytes. Usato per: validazione lato server, "
            "presigned URL condition, verifica HEAD post-upload. Default 50 MB."
        ),
    )

    upload_presign_ttl_seconds: int = Field(
        default=15 * 60,  # 15 minuti
        gt=0,
        le=60 * 60,  # max 1 ora (security: TTL brevi limitano il blast radius)
        description=(
            "Durata di vita del presigned URL prima che B2 lo rifiuti. "
            "Default 15 minuti. Massimo accettato: 1 ora."
        ),
    )

    @model_validator(mode="after")
    def _validate_jwt_credentials(self) -> Self:
        """Garantisce che la credential corrispondente all'algoritmo sia presente.

        Senza questo, scopriremmo l'errore solo a runtime, alla prima richiesta
        autenticata. Con il validator, l'app non parte se la config è incoerente.
        """
        if self.supabase_jwt_algorithm == "HS256" and self.supabase_jwt_secret is None:
            raise ValueError(
                "supabase_jwt_secret è obbligatorio quando supabase_jwt_algorithm=HS256"
            )
        if self.supabase_jwt_algorithm == "ES256" and self.supabase_jwt_public_key is None:
            raise ValueError(
                "supabase_jwt_public_key è obbligatorio quando supabase_jwt_algorithm=ES256"
            )
        return self

    @model_validator(mode="after")
    def _validate_b2_credentials_in_production(self) -> Self:
        """In produzione, le credenziali B2 sono obbligatorie.

        In dev/staging restano opzionali: dev usa moto (mock S3) e staging
        può puntare a un bucket di test diverso. Solo in production l'assenza
        è un errore di configurazione che deve fallire all'avvio.
        """
        if self.app_env != "production":
            return self

        missing: list[str] = []
        if self.b2_key_id is None:
            missing.append("b2_key_id")
        if self.b2_application_key is None:
            missing.append("b2_application_key")
        if self.b2_bucket_name is None:
            missing.append("b2_bucket_name")
        if self.b2_endpoint is None:
            missing.append("b2_endpoint")
        if missing:
            raise ValueError(
                f"In produzione le variabili B2 sono obbligatorie. Mancanti: {', '.join(missing)}"
            )
        return self

    # -------------------------------------------------------------------------
    # Configurazione del loader Pydantic
    # -------------------------------------------------------------------------
    # `env_file=("../.env", ".env")` cerca .env prima nel parent (root del repo,
    # dove vive il vero file) poi nella cwd del processo (utile in test).
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignora variabili extra in .env (es. NEO4J_*, OPENAI_*: arrivano dopo)
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

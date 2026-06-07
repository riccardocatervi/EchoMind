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
from typing import Annotated, Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    # -------------------------------------------------------------------------
    # Async jobs — Celery + RabbitMQ (broker) + Redis (result backend) — M3
    # -------------------------------------------------------------------------
    # NB: rabbitmq_url/redis_url sono `str`, NON AmqpDsn/RedisDsn, di proposito.
    # I validator URL di Pydantic normalizzano il path (es. slash finale), ma
    # per AMQP lo slash finale CODIFICA il virtual host: "amqp://.../" --> vhost
    # vuoto, "amqp://...//" --> vhost "/". Normalizzarlo cambierebbe il vhost per
    # sbaglio (footgun classico di Celery). Lasciamo la stringa intatta: kombu
    # la parsa e fallisce in modo esplicito se è malformata.
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description=(
            "URL broker AMQP per Celery. Source env: RABBITMQ_URL. "
            "Default = RabbitMQ dev locale (vhost '/' via doppio slash finale)."
        ),
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL Redis usato come result backend Celery. Source env: REDIS_URL.",
    )

    task_max_retries: int = Field(
        default=3,
        ge=0,
        description=(
            "Retry massimi di un task prima dello stato terminale 'failed' "
            "(che dead-lettera il messaggio nella DLQ)."
        ),
    )

    task_retry_backoff_seconds: int = Field(
        default=2,
        gt=0,
        description="Base del backoff esponenziale tra i retry (secondi): ritardo ≈ base * 2**attempt.",
    )

    task_soft_time_limit_seconds: int = Field(
        default=300,
        gt=0,
        description="Soft time limit per task (secondi): oltre, Celery solleva SoftTimeLimitExceeded.",
    )

    celery_task_always_eager: bool = Field(
        default=False,
        description=(
            "Se True i task girano in-process, sincroni (solo debug manuale). "
            "I test NON lo usano: confligge con l'event loop di pytest-asyncio (vedi ADR-0005)."
        ),
    )

    # -------------------------------------------------------------------------
    # Media processing — OpenAI Whisper (trascrizione audio) — M4
    # -------------------------------------------------------------------------
    # openai_api_key e' opzionale come le credenziali B2: in dev/test i worker
    # non girano e i test mockano il transcriber. Diventa necessaria solo quando
    # il worker trascrive davvero un audio --> get_worker_transcriber() solleva
    # un errore esplicito se manca. Source: platform.openai.com/api-keys.
    openai_api_key: SecretStr | None = Field(
        default=None,
        description=(
            "API key OpenAI per Whisper. Source env: OPENAI_API_KEY. Opzionale: il "
            "worker fallisce in modo esplicito se assente quando serve la trascrizione."
        ),
    )

    openai_org_id: str | None = Field(
        default=None,
        description="Organization ID OpenAI (opzionale). Source env: OPENAI_ORG_ID.",
    )

    whisper_model: str = Field(
        default="whisper-1",
        description=(
            "Modello di trascrizione OpenAI. Default 'whisper-1' (stabile, supporta audio lunghi)."
        ),
    )

    whisper_max_chunk_bytes: int = Field(
        default=24 * 1024 * 1024,  # 24 MB
        gt=0,
        description=(
            "Soglia di dimensione oltre la quale l'audio viene spezzato in chunk prima di "
            "Whisper. Sotto il limite hard di 25 MB di Whisper, con margine."
        ),
    )

    transcription_soft_time_limit_seconds: int = Field(
        default=1800,  # 30 minuti
        gt=0,
        description=(
            "Soft time limit dedicato al task di trascrizione (secondi). Piu' alto del "
            "task_soft_time_limit_seconds generico: l'audio lungo (chunked) richiede minuti."
        ),
    )

    # -------------------------------------------------------------------------
    # Knowledge graph — Neo4j (M5)
    # -------------------------------------------------------------------------
    # Opzionali in dev (i test mockano il grafo); obbligatori in produzione via
    # validator (come B2). In dev locale puntano al container Neo4j di compose.
    neo4j_uri: str | None = Field(
        default=None,
        description=(
            "URI Bolt di Neo4j. Source env: NEO4J_URI. Dev locale: bolt://localhost:7687; "
            "AuraDB: neo4j+s://xxxx.databases.neo4j.io. Obbligatorio se app_env=production."
        ),
    )

    neo4j_user: str = Field(
        default="neo4j",
        description="Username Neo4j. Source env: NEO4J_USER. Default 'neo4j'.",
    )

    neo4j_password: SecretStr | None = Field(
        default=None,
        description=(
            "Password Neo4j. Source env: NEO4J_PASSWORD. Obbligatoria se app_env=production."
        ),
    )

    # -------------------------------------------------------------------------
    # Knowledge extraction — Gemini / Google AI Studio (M5)
    # -------------------------------------------------------------------------
    # Un'unica credenziale per estrazione grafo, riassunto ed embeddings. Opzionale
    # come le altre credenziali esterne: il worker fallisce in modo esplicito
    # (require_secret) se assente quando serve davvero l'estrazione.
    gemini_api_key: SecretStr | None = Field(
        default=None,
        description=(
            "API key Google AI Studio per Gemini (estrazione + riassunto + embeddings). "
            "Source env: GEMINI_API_KEY. Free tier su aistudio.google.com."
        ),
    )

    gemini_model: str = Field(
        default="gemini-flash-latest",
        description=(
            "Modello Gemini per estrazione e riassunto. Source env: GEMINI_MODEL. "
            "ID esatto da AI Studio (es. 'gemini-3-flash'); default segue l'ultimo Flash."
        ),
    )

    gemini_embedding_model: str = Field(
        default="gemini-embedding-001",
        description="Modello Gemini per gli embeddings. Source env: GEMINI_EMBEDDING_MODEL.",
    )

    embedding_dimensions: int = Field(
        default=768,
        gt=0,
        description=(
            "Dimensione del vettore di embedding richiesta al modello e larghezza della "
            "colonna pgvector. DEVE combaciare con la migration 0005 (vector(768))."
        ),
    )

    extraction_max_chunk_chars: int = Field(
        default=12000,
        gt=0,
        description="Dimensione massima (caratteri) di un chunk di testo passato all'LLM.",
    )

    extraction_chunk_overlap_chars: int = Field(
        default=500,
        ge=0,
        description=(
            "Sovrapposizione (caratteri) tra chunk consecutivi: preserva il contesto ai confini."
        ),
    )

    entity_dedup_similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Soglia di similarita' coseno oltre cui due entita' sono considerate la stessa.",
    )

    extraction_soft_time_limit_seconds: int = Field(
        default=1800,  # 30 minuti
        gt=0,
        description=(
            "Soft time limit del task di estrazione (secondi). Alto come la trascrizione: "
            "molte chiamate LLM su documenti lunghi richiedono minuti."
        ),
    )

    # -------------------------------------------------------------------------
    # Frontend / CORS (M6)
    # -------------------------------------------------------------------------
    # Origini ammesse per le richieste cross-origin del browser. La SPA React e'
    # servita da host:porta diversi dall'API (es. http://localhost:5173): senza
    # CORS il browser blocca ogni fetch e il preflight OPTIONS dell'upload.
    # NoDecode disabilita il parsing JSON automatico di pydantic-settings, cosi'
    # il validator sotto accetta anche una comoda stringa CSV da env.
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173"],
        description=(
            "Origini ammesse per CORS. Lista JSON o stringa CSV "
            "(es. 'http://localhost:5173,https://app.example.com'). "
            "Default: il dev server Vite."
        ),
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accetta una stringa CSV oltre alla lista per CORS_ALLOW_ORIGINS.

        Da env e' molto piu' comodo scrivere "a,b,c" che '["a","b","c"]'. Se il
        valore e' gia' una lista (default o costruttore nei test), lo lascia stare.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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

    @model_validator(mode="after")
    def _validate_extraction_credentials_in_production(self) -> Self:
        """In produzione, Neo4j e Gemini sono obbligatori (come B2).

        In dev/staging restano opzionali: i test mockano grafo ed LLM, e il
        worker fallisce in modo esplicito (require_secret / GraphStore) se
        mancano quando servono davvero. Solo in production l'assenza e' un
        errore di configurazione che deve fallire all'avvio (fail fast).
        """
        if self.app_env != "production":
            return self

        missing: list[str] = []
        if self.neo4j_uri is None:
            missing.append("neo4j_uri")
        if self.neo4j_password is None:
            missing.append("neo4j_password")
        if self.gemini_api_key is None:
            missing.append("gemini_api_key")
        if missing:
            raise ValueError(
                "In produzione le variabili di knowledge extraction sono obbligatorie. "
                f"Mancanti: {', '.join(missing)}"
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
        extra="ignore",  # ignora variabili extra in .env (es. ANTHROPIC_*, SENTRY_*: arrivano dopo)
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


def require_secret(secret: SecretStr | None, *, env_name: str, hint: str = "") -> str:
    """Estrae il valore di un SecretStr trattando vuoto/whitespace come ASSENTE.

    Perche' esiste (debito tecnico saldato da M5, originato in M4): il
    placeholder vuoto nel .env produce `SecretStr("")`, che NON e' `None`. Un
    controllo `if secret is None` lascia passare la stringa vuota, che raggiunge
    il servizio esterno e provoca un errore di autenticazione criptico a runtime,
    invece di un chiaro errore di configurazione all'uso.

    Centralizziamo qui la regola "key valida = non vuota dopo strip" cosi' tutte
    le factory del worker (Whisper, Gemini, ...) la condividono.

    Args:
        secret: il SecretStr da validare (o None se la var non e' settata).
        env_name: nome della variabile d'ambiente, citato nell'errore.
        hint: testo opzionale che spiega a cosa serve la key.

    Returns:
        Il valore della key, garantito non vuoto.

    Raises:
        RuntimeError: se la key e' assente o vuota/whitespace.
    """
    value = secret.get_secret_value() if secret is not None else ""
    cleaned = value.strip()
    if not cleaned:
        message = f"{env_name} mancante o vuoto."
        if hint:
            message = f"{message} {hint}"
        raise RuntimeError(message)
    return cleaned

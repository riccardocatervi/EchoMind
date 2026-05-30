"""Test della configurazione Pydantic Settings.

Verifica:
- Variabili obbligatorie causano errore se mancanti
- Validazione tipi (URL, Literal)
- SecretStr non leakka il valore nel repr
- get_settings() è un singleton (lru_cache)
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from echomind.core.config import Settings, get_settings

# -----------------------------------------------------------------------------
# Helper: env vars minimi e validi per costruire un Settings di test
# -----------------------------------------------------------------------------
VALID_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/dbname",
    "SUPABASE_JWT_SECRET": "test-secret-at-least-32-chars-long-xxxxxxx",
}


def test_settings_loads_with_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: con env validi, Settings si costruisce senza errori."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    # _env_file=None: ignora il .env reale del repo, usa solo env vars.
    # Senza questo, il .env può "vincere" sui default e far fallire le
    # asserzioni che si aspettano i default.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_env == "development"  # default
    assert settings.log_level == "INFO"  # default
    assert str(settings.database_url).startswith("postgresql+asyncpg://")
    assert settings.supabase_jwt_algorithm == "HS256"
    assert settings.supabase_jwt_audience == "authenticated"


def test_settings_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Senza DATABASE_URL, l'app deve fallire all'avvio (fail-fast)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", VALID_ENV["SUPABASE_JWT_SECRET"])

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]

    # Verifica che l'errore citi proprio database_url
    assert "database_url" in str(exc_info.value).lower()


def test_settings_jwt_secret_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Senza SUPABASE_JWT_SECRET, fail-fast."""
    monkeypatch.setenv("DATABASE_URL", VALID_ENV["DATABASE_URL"])
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert "supabase_jwt_secret" in str(exc_info.value).lower()


def test_settings_rejects_invalid_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL malformati devono essere rifiutati."""
    monkeypatch.setenv("DATABASE_URL", "not-a-valid-url")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", VALID_ENV["SUPABASE_JWT_SECRET"])

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_rejects_invalid_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """app_env è Literal: valori fuori dall'enum sono rifiutati."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "qa")  # non in Literal[...]

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_secret_str_does_not_leak_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """SecretStr deve mascherare il valore in repr/str/print.

    Questo è il motivo per cui usiamo SecretStr e non `str` semplice:
    un log accidentale di settings non espone il segreto.
    """
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    rendered = repr(settings)
    assert VALID_ENV["SUPABASE_JWT_SECRET"] not in rendered
    assert "**********" in rendered or "SecretStr" in rendered

    # Per ottenere il valore vero serve la chiamata esplicita
    assert isinstance(settings.supabase_jwt_secret, SecretStr)
    assert settings.supabase_jwt_secret.get_secret_value() == VALID_ENV["SUPABASE_JWT_SECRET"]


def test_get_settings_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() ritorna sempre la stessa istanza (lru_cache)."""
    # Non possiamo passare _env_file=None qui (get_settings() non accetta
    # parametri), quindi anneghiamo le variabili di .env settando esplicitamente
    # quelle che potrebbero confonderci.
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SUPABASE_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", "")
    get_settings.cache_clear()  # reset prima del test

    first = get_settings()
    second = get_settings()

    assert first is second  # stessa identità in memoria, non solo uguaglianza


def test_case_insensitive_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """case_sensitive=False: database_url e DATABASE_URL sono equivalenti."""
    monkeypatch.setenv("database_url", VALID_ENV["DATABASE_URL"])  # lowercase
    monkeypatch.setenv("supabase_jwt_secret", VALID_ENV["SUPABASE_JWT_SECRET"])

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert str(settings.database_url).startswith("postgresql+asyncpg://")


# =============================================================================
# B2 + upload limits (M2)
# =============================================================================
def test_b2_credentials_optional_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """In dev, le credenziali B2 sono opzionali (default None)."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "development")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.b2_key_id is None
    assert settings.b2_application_key is None
    assert settings.b2_bucket_name is None
    assert settings.b2_endpoint is None
    # Default per region e limiti
    assert settings.b2_region == "eu-central-003"
    assert settings.max_upload_size_bytes == 50 * 1024 * 1024
    assert settings.upload_presign_ttl_seconds == 15 * 60


def test_b2_credentials_required_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """In produzione, l'assenza di credenziali B2 deve far fallire all'avvio."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "production")
    # Nessuna B2_* settata

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]

    error_msg = str(exc_info.value).lower()
    # Il validator deve elencare TUTTE le variabili mancanti
    assert "b2_key_id" in error_msg
    assert "b2_application_key" in error_msg
    assert "b2_bucket_name" in error_msg
    assert "b2_endpoint" in error_msg


def test_b2_credentials_complete_in_production_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In produzione, con TUTTE le B2 settate l'app parte senza errori."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("B2_KEY_ID", "prod-key-id-dummy")
    monkeypatch.setenv("B2_APPLICATION_KEY", "prod-app-key-dummy-secret")
    monkeypatch.setenv("B2_BUCKET_NAME", "echomind-prod")
    monkeypatch.setenv("B2_ENDPOINT", "https://s3.eu-central-003.backblazeb2.com")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.b2_bucket_name == "echomind-prod"
    assert settings.b2_endpoint == "https://s3.eu-central-003.backblazeb2.com"


def test_upload_presign_ttl_capped_at_one_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTL > 1 ora rifiutato (limite di sicurezza: blast radius del leak URL)."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("UPLOAD_PRESIGN_TTL_SECONDS", "3601")  # 1h + 1s

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_max_upload_size_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    """`max_upload_size_bytes` deve essere strettamente positivo."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


# =============================================================================
# Async jobs (M3): Celery + RabbitMQ + Redis
# =============================================================================
def test_async_jobs_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Senza env dedicate, i parametri dei job hanno default sensati (dev locale)."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.rabbitmq_url.startswith("amqp://")
    assert settings.redis_url.startswith("redis://")
    assert settings.task_max_retries == 3
    assert settings.task_retry_backoff_seconds == 2
    assert settings.task_soft_time_limit_seconds == 300
    assert settings.celery_task_always_eager is False


def test_task_max_retries_rejects_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    """task_max_retries >= 0 (un valore negativo non ha senso)."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TASK_MAX_RETRIES", "-1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_task_retry_backoff_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    """La base del backoff deve essere strettamente positiva."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TASK_RETRY_BACKOFF_SECONDS", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]

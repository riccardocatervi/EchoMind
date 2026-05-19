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

    settings = Settings()  # type: ignore[call-arg]

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

    settings = Settings()  # type: ignore[call-arg]

    rendered = repr(settings)
    assert VALID_ENV["SUPABASE_JWT_SECRET"] not in rendered
    assert "**********" in rendered or "SecretStr" in rendered

    # Per ottenere il valore vero serve la chiamata esplicita
    assert isinstance(settings.supabase_jwt_secret, SecretStr)
    assert settings.supabase_jwt_secret.get_secret_value() == VALID_ENV["SUPABASE_JWT_SECRET"]


def test_get_settings_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() ritorna sempre la stessa istanza (lru_cache)."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
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

"""Test della configurazione di logging.

Verifica:
- configure_logging() non solleva eccezioni
- get_logger() ritorna un logger usabile
- request_id_var si propaga nei log emessi durante il contesto
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from echomind.core.logging import configure_logging, get_logger, request_id_var


@pytest.fixture(autouse=True)
def reset_logging() -> Iterator[None]:
    """Reset stato globale del logging dopo ogni test.

    structlog mantiene configurazione globale; tra test va azzerata
    per evitare interferenze (test isolation).
    """
    yield
    import structlog

    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def test_configure_logging_does_not_raise() -> None:
    """Smoke: configure_logging non deve esplodere su input validi."""
    configure_logging(log_level="INFO", json_logs=False)
    configure_logging(log_level="DEBUG", json_logs=True)


def test_get_logger_returns_usable_logger(capsys: pytest.CaptureFixture[str]) -> None:
    """get_logger restituisce un oggetto che accetta .info(event, **kwargs)."""
    configure_logging(log_level="INFO", json_logs=True)
    log = get_logger("test")

    log.info("hello_world", foo="bar", number=42)
    captured = capsys.readouterr().out

    # Output JSON deve contenere i campi
    payload = json.loads(captured.strip().splitlines()[-1])
    assert payload["event"] == "hello_world"
    assert payload["foo"] == "bar"
    assert payload["number"] == 42
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_log_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    """log_level=WARNING filtra eventi info/debug."""
    configure_logging(log_level="WARNING", json_logs=True)
    log = get_logger("test")

    log.info("this_should_be_filtered")
    log.warning("this_should_appear")

    captured = capsys.readouterr().out
    assert "this_should_be_filtered" not in captured
    assert "this_should_appear" in captured


def test_request_id_propagation(capsys: pytest.CaptureFixture[str]) -> None:
    """request_id_var setta un context var che appare in tutti i log."""
    configure_logging(log_level="INFO", json_logs=True)
    log = get_logger("test")

    token = request_id_var.set("req-abc-123")
    try:
        log.info("inside_context")
    finally:
        request_id_var.reset(token)

    log.info("outside_context")

    output_lines = capsys.readouterr().out.strip().splitlines()
    inside = json.loads(output_lines[-2])
    outside = json.loads(output_lines[-1])

    assert inside["event"] == "inside_context"
    assert inside["request_id"] == "req-abc-123"

    assert outside["event"] == "outside_context"
    assert "request_id" not in outside  # propagazione SOLO dentro il context


def test_bound_context_carried_across_calls(capsys: pytest.CaptureFixture[str]) -> None:
    """Il logger può essere "bound" con contesto persistente."""
    configure_logging(log_level="INFO", json_logs=True)
    log = get_logger("test", component="upload", version="1")

    log.info("first")
    log.info("second")

    output_lines = capsys.readouterr().out.strip().splitlines()
    first = json.loads(output_lines[-2])
    second = json.loads(output_lines[-1])

    # Il contesto bound è presente in entrambi i log
    assert first["component"] == "upload"
    assert first["version"] == "1"
    assert second["component"] == "upload"
    assert second["version"] == "1"

"""Logging strutturato basato su structlog.

Filosofia:
- **Eventi**, non stringhe: ogni log è un evento con campi (key=value).
- **Stessa API**, output diverso per dev (leggibile) e prod (JSON).
- **Context propagation** via contextvars: request_id, user_id si propagano
  automaticamente in tutti i log emessi durante la richiesta.

Pattern d'uso:

    from echomind.core.logging import get_logger

    log = get_logger(__name__)
    log.info("file_uploaded", user_id=str(uid), file_size=1024)

In produzione → JSON line per ogni log, ingeribile da ELK/Datadog/Loki.
In dev → output colorato e indentato, ideale per debugging.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import EventDict, Processor

# -----------------------------------------------------------------------------
# Context propagation
# -----------------------------------------------------------------------------
# ContextVar è il modo async-safe di mantenere stato per-request in Python.
# A differenza di una variabile globale, ogni task asyncio ha la sua copia.
# Quando il middleware in main.py setterà `request_id_var.set(uuid)`, tutti
# i log emessi durante quella richiesta includeranno il request_id.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Processor structlog: copia request_id_var nei campi del log, se presente.

    I "processor" sono funzioni che ricevono il dict dell'evento e lo
    trasformano. Componibili → catena dichiarativa in `configure_logging()`.
    """
    request_id = request_id_var.get()
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


# -----------------------------------------------------------------------------
# Configurazione
# -----------------------------------------------------------------------------
def configure_logging(*, log_level: str, json_logs: bool) -> None:
    """Configura structlog + stdlib logging in modo coerente.

    Args:
        log_level: soglia minima ("DEBUG", "INFO", ...). Lower = più verboso.
        json_logs: True → JSON renderer (prod/staging); False → console (dev).

    Questa funzione va chiamata UNA VOLTA all'avvio dell'app, prima di
    qualunque emit di log. Tipicamente nel lifespan/startup di FastAPI.
    """

    # Catena di processor: ordine = pipeline. Ogni step può modificare l'event dict.
    shared_processors: list[Processor] = [
        # Aggiunge il nome del logger (es. "echomind.api.profiles")
        structlog.stdlib.add_logger_name,
        # Aggiunge "level": "info" / "warning" / ...
        structlog.stdlib.add_log_level,
        # Aggiunge "timestamp": ISO8601 UTC
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Propaga request_id_var nei campi del log
        _add_request_id,
        # Se passi exc_info=True, lo serializza in modo strutturato
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Concatena log message (positional args) in un singolo "event" field
        structlog.processors.UnicodeDecoder(),
    ]

    # Renderer finale: JSON in prod, console colorato in dev.
    if json_logs:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        # Logger underlying: stdlib (così integrazione con librerie terze parti che
        # usano `logging` standard, es. uvicorn, sqlalchemy).
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[log_level.upper()]
        ),
        # cache_logger_on_first_use=True: il logger per modulo è creato una sola
        # volta. Performance + identità stabile.
        cache_logger_on_first_use=True,
    )

    # Configura anche lo stdlib logging in modo che i log di librerie terze
    # (uvicorn, sqlalchemy, ecc.) seguano lo stesso formato e livello.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))  # structlog rende il dict
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())

    # Riduci verbosità di librerie troppo loquaci (regola comune).
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None, **initial_values: Any) -> BoundLogger:
    """Ritorna un BoundLogger per il modulo specificato.

    Uso tipico, top-level del modulo:

        log = get_logger(__name__)

    Oppure con contesto già bound:

        log = get_logger(__name__, component="upload")
        log.info("file_received", size=1024)
        # → {"event": "file_received", "component": "upload", "size": 1024, ...}
    """
    # structlog.get_logger ritorna `Any` → cast esplicito per tipi.
    logger = cast(BoundLogger, structlog.get_logger(name))
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger

"""Alembic env — orchestratore delle migration.

Due modalità di esecuzione:

- **online** (default): apre una connessione vera al DB, applica le
  migration una per una in transazione.

- **offline**: NON si connette al DB, genera SQL stampato a stdout.
  Utile per: code review SQL, applicazione manuale in ambienti con DBA.

In entrambi i casi, il "target metadata" (= la sorgente di verità dello schema
desiderato) sono i modelli SQLAlchemy importati da `echomind.db.models`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import dei modelli: ogni modello qui presente diventa visibile ad Alembic
# (necessario per autogenerate e per costruire Base.metadata).
# Importare il modulo che ri-esporta tutto è sufficiente.
import echomind.db.models  # noqa: F401  (import for side-effect: register tables)
from echomind.core.config import get_settings
from echomind.db.base import Base

# Alembic Config: legge alembic.ini, accesso a CLI args via context.config
config = context.config

# Configura logging Alembic da alembic.ini (sezione [loggers])
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata target: tutto lo schema che dovremmo avere a regime
target_metadata = Base.metadata

# Iniettiamo la URL del DB da Pydantic Settings (non da alembic.ini).
# Vantaggio: la stessa Settings è single source of truth per app + migration.
_settings = get_settings()
config.set_main_option("sqlalchemy.url", str(_settings.database_url))


# -----------------------------------------------------------------------------
# Configurazione comune ai due modi (online/offline)
# -----------------------------------------------------------------------------
def _include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Filtro: cosa Alembic deve considerare nei diff autogenerati.

    Escludiamo lo schema `auth` dall'autogenerate: è gestito da Supabase
    in prod e dalla migration manuale in dev. Non vogliamo che Alembic
    proponga di "rimuoverlo" ogni volta.
    """
    return not (type_ == "table" and hasattr(obj, "schema") and obj.schema == "auth")  # type: ignore[attr-defined]


# -----------------------------------------------------------------------------
# Offline: emette SQL su stdout senza connettersi al DB
# -----------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Genera lo script SQL senza eseguirlo."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------------
# Online: si connette al DB e applica le migration
# -----------------------------------------------------------------------------
def _do_run_migrations(connection: Connection) -> None:
    """Step sincrono dentro il callback async."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        compare_type=True,
        compare_server_default=True,
        # Naming convention deve matchare quella di Base
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Esecuzione online con async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # niente connection pool per migration (one-shot)
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

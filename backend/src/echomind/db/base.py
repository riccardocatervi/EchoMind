"""DeclarativeBase comune per tutti i modelli SQLAlchemy.

Centralizziamo qui:
1. La classe `Base` da cui ereditano i modelli (`class Profile(Base): ...`)
2. La **naming convention** dei constraint (PK, FK, indici, ...)

Perché la naming convention è importante:
    Senza, il DB sceglie nomi a piacere (es. `profiles_pkey`, `idx_random`).
    Su Postgres vs SQLite gli stessi modelli generano migrazioni Alembic
    diverse → diff sporchi, rollback imprevedibili.

    Con questa convention, OGNI constraint ha un nome deterministico
    basato sulla tabella + colonne. Es:
      - PK: "pk_profiles"
      - FK: "fk_profiles_owner_users"
      - Index: "ix_profiles_created_at"
      - Unique: "uq_profiles_email"
      - Check: "ck_profiles_role_valid"

Riferimento: https://alembic.sqlalchemy.org/en/latest/naming.html
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convention per i nomi auto-generati di constraint e indici.
# Le chiavi (`pk`, `fk`, `ix`, `uq`, `ck`) sono short-code SQLAlchemy:
#   pk = primary key, fk = foreign key, ix = index,
#   uq = unique constraint, ck = check constraint
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base comune per tutti i modelli ORM.

    Eredita da DeclarativeBase (SQLAlchemy 2.0+) e applica la naming convention.
    Tutti i modelli del progetto DEVONO ereditare da questa classe.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

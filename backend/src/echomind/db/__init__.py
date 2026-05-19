"""Database layer.

Contiene:
- `base`: DeclarativeBase comune a tutti i modelli SQLAlchemy
- `session`: engine async, sessionmaker, helper per RLS

I modelli vivono in `db/models/`, i repository in `db/repositories/`.
"""

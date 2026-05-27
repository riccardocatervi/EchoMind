"""SQLAlchemy ORM models.

Convenzione:
- Un modulo per modello (`profile.py`, in futuro `document.py`, ecc.)
- Modelli importati qui per consentire ad Alembic di "vederli tutti"
  con un singolo `from echomind.db.models import *` nel suo env.py

Niente import qui di cose non-modello (services, repositories) per
evitare cicli import.
"""

from echomind.db.models.profile import Profile

__all__ = ["Profile"]

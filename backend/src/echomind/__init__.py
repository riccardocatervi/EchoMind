"""EchoMind backend package.

Esporta solo la versione. Niente import di sottomoduli qui: import al
top-level rallenta l'avvio e crea cicli di import difficili da debuggare.
"""

from echomind._version import __version__

__all__ = ["__version__"]

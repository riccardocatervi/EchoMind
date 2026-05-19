"""Smoke test della pipeline.

Scopo: verificare che il package sia installato correttamente, che pytest sia
configurato e che la CI esegua almeno un test passante. Quando questo file
fallisce, è segno che qualcosa è rotto a livello di tooling, non di codice
applicativo.
"""

from echomind import __version__


def test_version_is_string() -> None:
    """La versione deve essere una stringa non vuota."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_follows_semver_shape() -> None:
    """Forma 'X.Y.Z' (validazione strutturale, non semver completo)."""
    parts = __version__.split(".")
    assert len(parts) == 3, f"Atteso 'X.Y.Z', trovato: {__version__!r}"
    assert all(p.isdigit() for p in parts), f"Componenti non numerici: {__version__!r}"

"""Lingue supportate per l'output generato (riassunto, grafo, risposte RAG).

EchoMind genera summary, descrizioni del grafo e risposte del Q&A nella lingua
SCELTA dall'utente nell'interfaccia, non nella lingua del documento. Questo modulo
centralizza l'insieme delle lingue supportate, il default e la mappa codice -> nome
inglese (usata nei prompt LLM, che ragionano meglio con "Italian"/"English" che con
i codici ISO).

Riusato da:
- schema profilo (validazione del PATCH preferred_language)
- worker (fallback quando il payload non porta una lingua)
- adapter Gemini (nome lingua nel prompt)
- endpoint RAG (parsing dell'header Accept-Language)
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "it"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en")

# Nome inglese della lingua: i modelli seguono meglio "Italian"/"English".
_LANGUAGE_NAMES: dict[str, str] = {"it": "Italian", "en": "English"}


def normalize_language(value: str | None) -> str:
    """Riduce un input arbitrario a un codice di lingua supportato.

    Prende solo la parte primaria del tag (es. 'en-US' -> 'en'), normalizza
    minuscolo e spazi e, se la lingua non e' riconosciuta, ripiega sul default
    (italiano). Tollerante a None/stringa vuota.

    Usata per: header Accept-Language, payload del task di estrazione,
    preferenza di profilo.
    """
    if value:
        code = value.strip().lower().split("-")[0]
        if code in SUPPORTED_LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def language_name(code: str) -> str:
    """Nome inglese della lingua, per i prompt LLM. Default difensivo: Italian."""
    return _LANGUAGE_NAMES.get(normalize_language(code), _LANGUAGE_NAMES[DEFAULT_LANGUAGE])

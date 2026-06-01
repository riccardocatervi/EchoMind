"""Normalizzazione del testo estratto/trascritto.

Il testo grezzo che esce da pypdf, python-docx o Whisper e' "sporco":
- newline eterogenei (\\r\\n di Windows, \\r del vecchio Mac);
- caratteri di controllo invisibili (form-feed dei PDF, NUL, ecc.);
- run di spazi/tab e righe vuote multiple;
- forme Unicode non canoniche (la stessa lettera accentata in 1 o 2 code point).

`normalize_text` produce una forma stabile e pulita: e' importante perche' il
contenuto finisce nel DB e, a valle (M5+), verra' spezzato e dato in pasto a un
LLM -- rumore di formattazione = token sprecati e chunk peggiori.

E' una funzione PURA (nessun I/O): banale da testare in isolamento.
"""

from __future__ import annotations

import re
import unicodedata

# Caratteri di controllo da rimuovere: tutto il range C0 TRANNE tab (\x09) e
# newline (\x0a), piu' il DEL (\x7f). I \r vengono prima convertiti in \n, quindi
# a questo punto non ne restano.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Run di spazi e tab (NON i newline) --> un singolo spazio.
_HORIZONTAL_WS = re.compile(r"[ \t]+")

# Tre o piu' newline consecutivi --> due (massimo una riga vuota tra i paragrafi).
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def normalize_text(raw: str) -> str:
    """Ripulisce e canonicalizza il testo.

    Passi (in ordine):
      1. normalizzazione Unicode NFC (forma canonica composta);
      2. unificazione dei newline (\\r\\n e \\r --> \\n);
      3. rimozione dei caratteri di controllo invisibili;
      4. collasso dei run di spazi/tab orizzontali in un singolo spazio;
      5. trim degli spazi a fine riga;
      6. collasso di 3+ righe vuote in una sola;
      7. strip finale.

    Ritorna stringa vuota se l'input e' vuoto o diventa vuoto dopo la pulizia
    (il chiamante lo interpreta come EmptyContentError).
    """
    if not raw:
        return ""

    text = unicodedata.normalize("NFC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = _HORIZONTAL_WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    return text.strip()

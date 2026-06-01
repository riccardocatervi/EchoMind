"""Estrazione di testo dai documenti testuali: PDF, DOCX, TXT.

Ogni estrattore prende i `bytes` grezzi e ritorna testo NON normalizzato (la
normalizzazione e' centralizzata nella pipeline, uguale per documenti e audio).
Gli errori delle librerie (file corrotto, formato sbagliato) vengono tradotti in
`DocumentParseError` -- un errore di dominio permanente, cosi' il worker non
sprechera' retry su un file che fallira' identico ogni volta.

Librerie:
- PDF:  pypdf (puro Python, nessuna dipendenza di sistema). Niente OCR: un PDF
        scansionato senza layer di testo produce stringa vuota --> a valle
        diventa EmptyContentError.
- DOCX: python-docx (import `docx`). Estrae i paragrafi del corpo.
- TXT:  decodifica bytes --> str, con fallback di encoding robusto.
"""

from __future__ import annotations

import io

from docx import Document as DocxDocument
from pypdf import PdfReader

from echomind.processing.errors import DocumentParseError, UnsupportedMediaTypeError

# MIME types dei documenti testuali (sottoinsieme della ALLOWED_MIME_TYPES di M2).
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_MIME = "text/plain"

DOCUMENT_MIME_TYPES = frozenset({PDF_MIME, DOCX_MIME, TXT_MIME})

# MIME --> etichetta breve di formato (usata nei meta del transcript).
DOCUMENT_FORMAT_LABELS = {PDF_MIME: "pdf", DOCX_MIME: "docx", TXT_MIME: "txt"}


def extract_document_text(*, mime_type: str, data: bytes) -> str:
    """Dispatch per MIME --> testo grezzo estratto.

    Raises:
        UnsupportedMediaTypeError: il MIME non e' un documento testuale.
        DocumentParseError: il file e' corrotto o illeggibile.
    """
    if mime_type == PDF_MIME:
        return _extract_pdf(data)
    if mime_type == DOCX_MIME:
        return _extract_docx(data)
    if mime_type == TXT_MIME:
        return _decode_txt(data)
    raise UnsupportedMediaTypeError(f"Tipo documento non supportato: {mime_type}")


def _extract_pdf(data: bytes) -> str:
    """Estrae il testo da tutte le pagine del PDF.

    I PDF cifrati con password vuota (caso comune: protezione solo "owner")
    vengono sbloccati al volo; quelli con password reale sono illeggibili
    --> DocumentParseError.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        # decrypt("") ritorna PasswordType.NOT_DECRYPTED (falsy) se la password
        # vuota non basta; lo valutiamo solo se il PDF e' cifrato (short-circuit).
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentParseError("PDF protetto da password: impossibile leggerlo")
        pages = [page.extract_text() or "" for page in reader.pages]
    except DocumentParseError:
        raise
    except Exception as exc:  # pypdf solleva vari tipi (PdfReadError, ecc.)
        raise DocumentParseError(f"PDF illeggibile o corrotto: {exc}") from exc
    return "\n".join(pages)


def _extract_docx(data: bytes) -> str:
    """Estrae il testo dai paragrafi del corpo del documento DOCX."""
    try:
        document = DocxDocument(io.BytesIO(data))
        paragraphs = [p.text for p in document.paragraphs]
    except Exception as exc:  # python-docx: PackageNotFoundError e altri
        raise DocumentParseError(f"DOCX illeggibile o corrotto: {exc}") from exc
    return "\n".join(paragraphs)


def _decode_txt(data: bytes) -> str:
    """Decodifica bytes --> testo.

    Prova prima UTF-8 (gestendo l'eventuale BOM con utf-8-sig). Se fallisce,
    ripiega su latin-1, che mappa tutti i 256 byte e quindi non solleva MAI:
    nel peggiore dei casi qualche carattere non-latino sara' reso male, ma non
    perdiamo il documento (scelta robustezza > purezza).
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")

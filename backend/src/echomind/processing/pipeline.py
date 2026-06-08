"""Orchestratore del media processing: bytes grezzi --> testo normalizzato.

`process_media` e' il punto d'ingresso unico e SINCRONO della pipeline. Dato il
MIME type e i byte di un file (gia' scaricati dallo storage dal worker), instrada
verso il ramo documento o audio, normalizza il testo e impacchetta il risultato.

Pura e deterministica a parita' di input + transcriber: i test la chiamano
direttamente con input "golden" (un PDF, un MP3, un TXT) e -- per l'audio -- un
`Transcriber` finto. Niente Celery, niente DB, niente rete.

Il worker (Checkpoint 13) la invoca via `asyncio.to_thread` e persiste il
`ProcessingResult` come riga `transcripts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from echomind.db.models import SourceType
from echomind.processing.audio import AUDIO_MIME_TYPES, prepare_audio_chunks
from echomind.processing.documents import (
    DOCUMENT_FORMAT_LABELS,
    DOCUMENT_MIME_TYPES,
    extract_document_text,
)
from echomind.processing.errors import (
    EmptyContentError,
    ProcessingError,
    UnsupportedMediaTypeError,
)
from echomind.processing.normalize import normalize_text
from echomind.processing.transcription import Transcriber

# Default allineato a Settings.whisper_max_chunk_bytes (24 MB): consente di
# chiamare process_media nei test senza passare la soglia esplicitamente.
DEFAULT_MAX_CHUNK_BYTES = 24 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Output della pipeline, pronto per diventare una riga `transcripts`."""

    source_type: SourceType
    content: str
    language: str | None
    meta: dict[str, Any]


def process_media(
    *,
    mime_type: str,
    data: bytes,
    transcriber: Transcriber | None = None,
    max_chunk_bytes: int = DEFAULT_MAX_CHUNK_BYTES,
) -> ProcessingResult:
    """Trasforma un file in testo normalizzato.

    Args:
        mime_type: MIME validato a monte (M2). Decide il ramo documento/audio.
        data: byte del file, gia' scaricati dallo storage.
        transcriber: necessario solo per l'audio; ignorato per i documenti.
        max_chunk_bytes: soglia di chunking audio (default 24 MB).

    Raises:
        UnsupportedMediaTypeError: MIME non gestito.
        DocumentParseError / AudioProcessingError / TranscriptionError: a seconda
            del ramo (vedi i rispettivi moduli).
        EmptyContentError: testo vuoto dopo la normalizzazione.
        ProcessingError: transcriber mancante per un input audio.
    """
    if mime_type in DOCUMENT_MIME_TYPES:
        return _process_document(mime_type=mime_type, data=data)
    if mime_type in AUDIO_MIME_TYPES:
        return _process_audio(
            mime_type=mime_type,
            data=data,
            transcriber=transcriber,
            max_chunk_bytes=max_chunk_bytes,
        )
    raise UnsupportedMediaTypeError(f"MIME type non gestito dalla pipeline: {mime_type}")


def _process_document(*, mime_type: str, data: bytes) -> ProcessingResult:
    raw = extract_document_text(mime_type=mime_type, data=data)
    content = normalize_text(raw)
    if not content:
        raise EmptyContentError(
            "Nessun testo estraibile dal documento "
            "(es. PDF scansionato senza layer di testo: in M4 non c'e' OCR)"
        )
    return ProcessingResult(
        source_type=SourceType.DOCUMENT,
        content=content,
        language=None,  # per i documenti non rileviamo la lingua
        meta={"source_format": DOCUMENT_FORMAT_LABELS[mime_type]},
    )


def _process_audio(
    *,
    mime_type: str,
    data: bytes,
    transcriber: Transcriber | None,
    max_chunk_bytes: int,
) -> ProcessingResult:
    if transcriber is None:
        # Errore di programmazione, non di input: il worker passa sempre un
        # transcriber. Permanente (retryable=False di default).
        raise ProcessingError("process_media: serve un transcriber per l'audio")

    chunks, duration_seconds = prepare_audio_chunks(
        data=data,
        mime_type=mime_type,
        max_chunk_bytes=max_chunk_bytes,
    )

    texts: list[str] = []
    language: str | None = None
    for chunk in chunks:
        result = transcriber.transcribe(audio=chunk.data, filename=chunk.filename)
        texts.append(result.text)
        # La lingua del primo chunk e' rappresentativa dell'intero audio.
        if language is None:
            language = result.language

    content = normalize_text("\n".join(texts))
    if not content:
        raise EmptyContentError("Trascrizione vuota: l'audio non conteneva parlato riconoscibile")

    return ProcessingResult(
        source_type=SourceType.AUDIO,
        content=content,
        language=language,
        meta={"chunks": len(chunks), "duration_seconds": round(duration_seconds, 2)},
    )

"""Media processing (M4): documenti/audio --> testo normalizzato.

Pacchetto di logica PURA e sincrona, indipendente da Celery, DB e FastAPI:
- `documents` : estrazione testo da PDF/DOCX/TXT
- `audio`     : segmentazione audio sotto il limite di Whisper
- `transcription` : Transcriber (Protocol) + implementazione OpenAI/Whisper
- `normalize` : pulizia e canonicalizzazione del testo
- `pipeline`  : `process_media`, l'orchestratore (punto d'ingresso unico)
- `errors`    : eccezioni di dominio con flag `retryable` (retry vs dead-letter)

Il worker (worker/tasks/transcribe.py) e' l'unico chiamante in produzione; i
test esercitano `process_media` direttamente con input golden + transcriber finto.
"""

from echomind.processing.audio import AUDIO_MIME_TYPES, AudioChunk, prepare_audio_chunks
from echomind.processing.documents import DOCUMENT_MIME_TYPES, extract_document_text
from echomind.processing.errors import (
    AudioProcessingError,
    DocumentParseError,
    EmptyContentError,
    ProcessingError,
    TranscriptionError,
    UnsupportedMediaTypeError,
)
from echomind.processing.normalize import normalize_text
from echomind.processing.pipeline import ProcessingResult, process_media
from echomind.processing.transcription import (
    OpenAIWhisperTranscriber,
    Transcriber,
    TranscriptionResult,
)

__all__ = [
    "AUDIO_MIME_TYPES",
    "DOCUMENT_MIME_TYPES",
    "AudioChunk",
    "AudioProcessingError",
    "DocumentParseError",
    "EmptyContentError",
    "OpenAIWhisperTranscriber",
    "ProcessingError",
    "ProcessingResult",
    "Transcriber",
    "TranscriptionError",
    "TranscriptionResult",
    "UnsupportedMediaTypeError",
    "extract_document_text",
    "normalize_text",
    "prepare_audio_chunks",
    "process_media",
]

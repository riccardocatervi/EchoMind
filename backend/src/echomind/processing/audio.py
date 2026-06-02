"""Segmentazione dell'audio prima della trascrizione Whisper.

Vincolo: l'endpoint Whisper rifiuta file oltre i 25 MB. Spezziamo l'audio in
chunk sotto la soglia (`whisper_max_chunk_bytes`, default 24 MB con margine)
PRIMA di inviarlo.

Strategia in due rami:
- File gia' sotto la soglia (la stragrande maggioranza): lo inviamo COSI' COM'E',
  senza ricodificarlo. Zero perdita di qualita', zero lavoro di ffmpeg.
- File troppo grande: lo carichiamo con pydub, lo dividiamo per TEMPO in N pezzi
  (N stimato dal rapporto byte/soglia) e ri-esportiamo ogni pezzo in MP3, formato
  compatto e ben supportato da Whisper. Splittare per tempo evita di tagliare a
  meta' un frame audio (cosa che accadrebbe spezzando i byte grezzi).

pydub richiede ffmpeg installato a livello di sistema (vedi pyproject / README).
Gli errori di decodifica diventano `AudioProcessingError` (permanente).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO
from math import ceil

from echomind.processing.errors import AudioProcessingError, UnsupportedMediaTypeError

# pydub emette al PROPRIO import alcuni warning innocui che vivono nel suo codice
# e che non possiamo correggere: regex con escape non validi (SyntaxWarning),
# 'audioop' deprecato (DeprecationWarning) e "ffmpeg non trovato" (RuntimeWarning,
# che a runtime gestiamo noi con AudioProcessingError). Li silenziamo SOLO attorno
# all'import: non indeboliamo i filtri globali dei test (filterwarnings=error) e
# manteniamo puliti anche i log del worker fuori da pytest.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from pydub import AudioSegment

# MIME --> (formato ffmpeg per la decodifica, estensione per il filename Whisper).
# L'estensione e' importante: Whisper deduce il formato dal nome file, non dai
# byte, quindi NON ci fidiamo del filename dell'utente ma lo deriviamo dal MIME.
_MIME_TO_FORMAT = {
    "audio/mpeg": ("mp3", ".mp3"),
    "audio/wav": ("wav", ".wav"),
    "audio/x-wav": ("wav", ".wav"),
    "audio/mp4": ("mp4", ".m4a"),
    "audio/x-m4a": ("mp4", ".m4a"),
}

AUDIO_MIME_TYPES = frozenset(_MIME_TO_FORMAT)


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """Un segmento audio pronto per Whisper.

    `filename` porta l'estensione corretta (es. '.mp3'): e' cosi' che Whisper
    riconosce il formato del contenuto.
    """

    data: bytes
    filename: str


def prepare_audio_chunks(
    *,
    data: bytes,
    mime_type: str,
    max_chunk_bytes: int,
) -> tuple[list[AudioChunk], float]:
    """Prepara i chunk audio da trascrivere e ritorna la durata totale.

    Returns:
        (chunks, duration_seconds). `chunks` ha 1 elemento se il file e' gia'
        sotto soglia, altrimenti N pezzi MP3.

    Raises:
        UnsupportedMediaTypeError: MIME audio non gestito.
        AudioProcessingError: audio non decodificabile o di durata nulla.
    """
    segment = _load_segment(data, mime_type)
    duration_seconds = len(segment) / 1000.0

    _, extension = _MIME_TO_FORMAT[mime_type]

    # Ramo veloce: il file ci sta gia' --> nessuna ricodifica.
    if len(data) <= max_chunk_bytes:
        return [AudioChunk(data=data, filename=f"audio{extension}")], duration_seconds

    # Ramo grande: split per tempo + ri-export in MP3.
    duration_ms = len(segment)
    if duration_ms <= 0:
        raise AudioProcessingError("Audio di durata nulla: niente da trascrivere")

    num_chunks = ceil(len(data) / max_chunk_bytes)
    chunk_ms = ceil(duration_ms / num_chunks)

    chunks: list[AudioChunk] = []
    for index in range(num_chunks):
        start_ms = index * chunk_ms
        if start_ms >= duration_ms:
            break
        end_ms = min(start_ms + chunk_ms, duration_ms)
        piece = segment[start_ms:end_ms]
        buffer = BytesIO()
        try:
            piece.export(buffer, format="mp3")
        except Exception as exc:
            raise AudioProcessingError(f"Export MP3 del chunk {index} fallito: {exc}") from exc
        chunks.append(AudioChunk(data=buffer.getvalue(), filename=f"chunk_{index}.mp3"))

    return chunks, duration_seconds


def _load_segment(data: bytes, mime_type: str) -> AudioSegment:
    """Carica l'audio con pydub/ffmpeg.

    Prova prima con il formato dedotto dal MIME; se fallisce, lascia che ffmpeg
    auto-rilevi il formato (alcune varianti m4a/wav sono etichettate in modo
    non standard). Se anche l'autodetect fallisce --> AudioProcessingError.
    """
    mapping = _MIME_TO_FORMAT.get(mime_type)
    if mapping is None:
        raise UnsupportedMediaTypeError(f"Tipo audio non supportato: {mime_type}")
    audio_format, _ = mapping

    try:
        return AudioSegment.from_file(BytesIO(data), format=audio_format)
    except Exception:
        try:
            return AudioSegment.from_file(BytesIO(data))
        except Exception as exc:
            raise AudioProcessingError(f"Audio non decodificabile ({mime_type}): {exc}") from exc

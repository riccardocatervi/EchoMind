"""Test della pipeline di processing (M4): funzioni PURE, niente DB ne' broker.

Copre:
- normalize_text: pulizia/canonicalizzazione del testo
- extract_document_text: PDF/DOCX/TXT (golden generati al volo) + errori
- process_media: instradamento documento/audio, EmptyContentError, MIME non gestito
- prepare_audio_chunks: ramo audio reale (skip se ffmpeg assente)
- OpenAIWhisperTranscriber: mappatura errori OpenAI --> TranscriptionError (mock client)
- errori: flag `retryable`

Per l'audio: ffmpeg e' richiesto da pydub. I test che decodificano audio REALE
sono marcati skipif; l'ORCHESTRAZIONE del ramo audio di process_media e' invece
coperta mockando prepare_audio_chunks (nessun ffmpeg), col transcriber finto.
"""

from __future__ import annotations

import shutil
from io import BytesIO
from types import SimpleNamespace
from typing import cast

import httpx
import openai
import pytest
from openai import OpenAI

from echomind.db.models import SourceType
from echomind.processing import (
    AudioChunk,
    DocumentParseError,
    EmptyContentError,
    OpenAIWhisperTranscriber,
    ProcessingError,
    TranscriptionError,
    TranscriptionResult,
    UnsupportedMediaTypeError,
    normalize_text,
    prepare_audio_chunks,
    process_media,
)

_HAS_FFMPEG = shutil.which("ffmpeg") is not None
requires_ffmpeg = pytest.mark.skipif(
    not _HAS_FFMPEG, reason="ffmpeg non installato (serve per il processing audio reale)"
)

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_MIME = "text/plain"


# =============================================================================
# Helper: generano documenti golden in memoria (niente file su disco)
# =============================================================================
def _make_pdf(text: str) -> bytes:
    """Costruisce un PDF a singola pagina spec-valido col testo dato.

    Calcola gli offset della xref table (niente warning di pypdf su xref rotta).
    `text` non deve contenere '(' ')' '\\' (caratteri speciali PDF non escapati).
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    content = b"BT /F1 24 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    objects.append(
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    size = len(objects) + 1
    pdf += b"xref\n0 " + str(size).encode() + b"\n"
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += b"trailer\n<< /Size " + str(size).encode() + b" /Root 1 0 R >>\n"
    pdf += b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"
    return bytes(pdf)


def _make_docx(paragraphs: list[str]) -> bytes:
    """Genera un .docx valido in memoria con python-docx."""
    from docx import Document as DocxDocument

    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# =============================================================================
# normalize_text
# =============================================================================
class TestNormalizeText:
    def test_empty_input_returns_empty(self) -> None:
        assert normalize_text("") == ""

    def test_strips_and_collapses_whitespace(self) -> None:
        assert normalize_text("  ciao    mondo  ") == "ciao mondo"

    def test_unifies_newlines_and_collapses_blank_lines(self) -> None:
        assert normalize_text("ciao\r\n\r\n\r\nmondo") == "ciao\n\nmondo"

    def test_removes_control_chars(self) -> None:
        assert normalize_text("ciao\x00\x07mondo") == "ciaomondo"

    def test_keeps_italian_accents(self) -> None:
        # NFC: gli accenti restano, non vengono spogliati.
        assert normalize_text("perche' e' gia' cosi'") == "perche' e' gia' cosi'"
        assert normalize_text("città") == "città"

    def test_whitespace_only_becomes_empty(self) -> None:
        assert normalize_text("   \n\t  \r\n ") == ""


# =============================================================================
# extract_document_text
# =============================================================================
class TestExtractDocumentText:
    def test_txt_utf8(self) -> None:
        from echomind.processing.documents import extract_document_text

        raw = extract_document_text(mime_type=TXT_MIME, data="ciao città".encode())
        assert "ciao città" in raw

    def test_txt_invalid_utf8_falls_back_to_latin1(self) -> None:
        from echomind.processing.documents import extract_document_text

        # 0xE8 = 'è' in latin-1, NON valido come UTF-8 standalone --> fallback.
        raw = extract_document_text(mime_type=TXT_MIME, data=b"caff\xe8")
        assert raw  # non solleva, ritorna qualcosa

    def test_docx_extracts_paragraphs(self) -> None:
        from echomind.processing.documents import extract_document_text

        data = _make_docx(["Primo paragrafo", "Secondo paragrafo"])
        raw = extract_document_text(mime_type=DOCX_MIME, data=data)
        assert "Primo paragrafo" in raw
        assert "Secondo paragrafo" in raw

    def test_pdf_extracts_text(self) -> None:
        from echomind.processing.documents import extract_document_text

        raw = extract_document_text(mime_type=PDF_MIME, data=_make_pdf("Hello PDF"))
        assert "Hello PDF" in raw

    def test_corrupt_pdf_raises_parse_error(self) -> None:
        from echomind.processing.documents import extract_document_text

        with pytest.raises(DocumentParseError):
            extract_document_text(mime_type=PDF_MIME, data=b"%PDF-1.4 garbage not a real pdf")

    def test_corrupt_docx_raises_parse_error(self) -> None:
        from echomind.processing.documents import extract_document_text

        with pytest.raises(DocumentParseError):
            extract_document_text(mime_type=DOCX_MIME, data=b"not a zip at all")

    def test_unsupported_mime_raises(self) -> None:
        from echomind.processing.documents import extract_document_text

        with pytest.raises(UnsupportedMediaTypeError):
            extract_document_text(mime_type="image/png", data=b"\x89PNG")


# =============================================================================
# process_media: ramo documenti
# =============================================================================
class TestProcessMediaDocuments:
    def test_txt_returns_document_result(self) -> None:
        result = process_media(mime_type=TXT_MIME, data=b"  ciao    mondo  ")
        assert result.source_type is SourceType.DOCUMENT
        assert result.content == "ciao mondo"  # normalizzato
        assert result.language is None
        assert result.meta == {"source_format": "txt"}

    def test_pdf_returns_document_result(self) -> None:
        result = process_media(mime_type=PDF_MIME, data=_make_pdf("Hello PDF"))
        assert result.source_type is SourceType.DOCUMENT
        assert "Hello PDF" in result.content
        assert result.meta["source_format"] == "pdf"

    def test_docx_returns_document_result(self) -> None:
        result = process_media(mime_type=DOCX_MIME, data=_make_docx(["Contenuto docx"]))
        assert result.source_type is SourceType.DOCUMENT
        assert "Contenuto docx" in result.content
        assert result.meta["source_format"] == "docx"

    def test_empty_text_raises_empty_content(self) -> None:
        with pytest.raises(EmptyContentError):
            process_media(mime_type=TXT_MIME, data=b"    \n\t  ")

    def test_unsupported_mime_raises(self) -> None:
        with pytest.raises(UnsupportedMediaTypeError):
            process_media(mime_type="image/png", data=b"\x89PNG")


# =============================================================================
# process_media: ramo audio (orchestrazione, prepare_audio_chunks mockato)
# =============================================================================
class TestProcessMediaAudio:
    def test_audio_stitches_chunks_and_detects_language(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Niente ffmpeg: mockiamo il chunking e iniettiamo un transcriber finto.

        Verifica che process_media: unisca i testi dei chunk, prenda la lingua dal
        primo chunk, e impacchetti meta con chunks + duration_seconds.
        """
        chunks = [
            AudioChunk(data=b"a", filename="c0.mp3"),
            AudioChunk(data=b"b", filename="c1.mp3"),
        ]
        monkeypatch.setattr(
            "echomind.processing.pipeline.prepare_audio_chunks",
            lambda **_kwargs: (chunks, 12.34),
        )

        outputs = iter(
            [
                TranscriptionResult(text="prima parte", language="italian"),
                TranscriptionResult(text="seconda parte", language=None),
            ]
        )

        class _FakeTranscriber:
            def transcribe(self, *, audio: bytes, filename: str) -> TranscriptionResult:
                return next(outputs)

        result = process_media(
            mime_type="audio/mpeg",
            data=b"fake-audio-bytes",
            transcriber=_FakeTranscriber(),
        )

        assert result.source_type is SourceType.AUDIO
        assert result.content == "prima parte\nseconda parte"
        assert result.language == "italian"  # dal primo chunk
        assert result.meta == {"chunks": 2, "duration_seconds": 12.34}

    def test_audio_without_transcriber_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "echomind.processing.pipeline.prepare_audio_chunks",
            lambda **_kwargs: ([AudioChunk(data=b"a", filename="c.mp3")], 1.0),
        )
        with pytest.raises(ProcessingError):
            process_media(mime_type="audio/mpeg", data=b"x", transcriber=None)

    def test_audio_empty_transcription_raises_empty_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "echomind.processing.pipeline.prepare_audio_chunks",
            lambda **_kwargs: ([AudioChunk(data=b"a", filename="c.mp3")], 1.0),
        )

        class _SilentTranscriber:
            def transcribe(self, *, audio: bytes, filename: str) -> TranscriptionResult:
                return TranscriptionResult(text="   ", language=None)

        with pytest.raises(EmptyContentError):
            process_media(mime_type="audio/mpeg", data=b"x", transcriber=_SilentTranscriber())


# =============================================================================
# prepare_audio_chunks: ramo reale (richiede ffmpeg)
# =============================================================================
class TestPrepareAudioChunks:
    @requires_ffmpeg
    def test_small_audio_single_chunk(self) -> None:
        """Audio sotto soglia --> un solo chunk, byte originali, durata corretta."""
        from pydub import AudioSegment

        buffer = BytesIO()
        AudioSegment.silent(duration=500).export(buffer, format="mp3")
        data = buffer.getvalue()

        chunks, duration = prepare_audio_chunks(
            data=data, mime_type="audio/mpeg", max_chunk_bytes=24 * 1024 * 1024
        )
        assert len(chunks) == 1
        assert chunks[0].data == data  # nessuna ricodifica
        assert chunks[0].filename.endswith(".mp3")
        assert duration == pytest.approx(0.5, abs=0.2)

    @requires_ffmpeg
    def test_large_audio_splits_into_multiple_chunks(self) -> None:
        """Audio sopra soglia --> piu' chunk MP3, ciascuno sotto la soglia."""
        from pydub import AudioSegment

        buffer = BytesIO()
        AudioSegment.silent(duration=4000).export(buffer, format="wav")
        data = buffer.getvalue()
        # Soglia minuscola per forzare lo split a prescindere dalla dimensione reale.
        max_bytes = max(1, len(data) // 4)

        chunks, _duration = prepare_audio_chunks(
            data=data, mime_type="audio/wav", max_chunk_bytes=max_bytes
        )
        assert len(chunks) >= 2
        assert all(len(c.data) <= max_bytes for c in chunks)


# =============================================================================
# Errori: flag retryable
# =============================================================================
class TestErrorRetryable:
    def test_base_processing_error_not_retryable(self) -> None:
        assert ProcessingError("x").retryable is False

    def test_transcription_error_retryable_by_default(self) -> None:
        assert TranscriptionError("x").retryable is True

    def test_transcription_error_can_be_forced_permanent(self) -> None:
        assert TranscriptionError("x", retryable=False).retryable is False

    def test_document_parse_error_not_retryable(self) -> None:
        assert DocumentParseError("x").retryable is False


# =============================================================================
# OpenAIWhisperTranscriber: mappatura errori (client OpenAI mockato)
# =============================================================================
_OPENAI_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")


def _openai_response(status: int) -> httpx.Response:
    return httpx.Response(status, request=_OPENAI_REQUEST)


class _FakeOpenAI:
    """Finto client OpenAI: la sua audio.transcriptions.create solleva o ritorna."""

    def __init__(self, *, exc: Exception | None = None, response: object | None = None) -> None:
        self._exc = exc
        self._response = response
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))

    def _create(self, **_kwargs: object) -> object:
        if self._exc is not None:
            raise self._exc
        return self._response


class TestWhisperTranscriber:
    @pytest.mark.parametrize(
        ("exc", "expected_retryable"),
        [
            (openai.APIConnectionError(request=_OPENAI_REQUEST), True),
            (openai.APITimeoutError(request=_OPENAI_REQUEST), True),
            (openai.RateLimitError("rate", response=_openai_response(429), body=None), True),
            (openai.InternalServerError("boom", response=_openai_response(500), body=None), True),
            (openai.BadRequestError("bad", response=_openai_response(400), body=None), False),
        ],
    )
    def test_error_mapping(self, exc: Exception, expected_retryable: bool) -> None:
        client = cast(OpenAI, _FakeOpenAI(exc=exc))
        transcriber = OpenAIWhisperTranscriber(client=client, model="whisper-1")
        with pytest.raises(TranscriptionError) as exc_info:
            transcriber.transcribe(audio=b"x", filename="a.mp3")
        assert exc_info.value.retryable is expected_retryable

    def test_success_returns_text_and_language(self) -> None:
        response = SimpleNamespace(text="ciao mondo", language="italian")
        client = cast(OpenAI, _FakeOpenAI(response=response))
        transcriber = OpenAIWhisperTranscriber(client=client, model="whisper-1")

        result = transcriber.transcribe(audio=b"x", filename="a.mp3")
        assert result.text == "ciao mondo"
        assert result.language == "italian"

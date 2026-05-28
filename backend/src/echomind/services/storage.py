"""B2StorageService — wrapper boto3 con S3-compatible API.

Scope: incapsula tutte le interazioni con Backblaze B2 dietro un'interfaccia
async di dominio. Il resto dell'app NON conosce boto3 / botocore.

Primitive esposte:
    - generate_presigned_put(key, content_type, content_length, ttl?)
        → ritorna (presigned_url, expires_at)
    - head_object(key) → ObjectMetadata (content_length, content_type)
    - get_object_range(key, start, end_inclusive) → bytes (per magic-bytes detect)
    - delete_object(key) → None

Pattern: ogni metodo wrappa la chiamata boto3 (sincrona) in `asyncio.to_thread`
per non bloccare l'event loop dell'app FastAPI.

Eccezioni:
    - StorageObjectNotFoundError: 404 / NoSuchKey su HEAD/GET/DELETE
    - StorageError: tutto il resto (network, 5xx, errori non recuperabili)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from echomind.core.config import Settings

if TYPE_CHECKING:
    # Import dei tipi solo per i type checker (mypy_boto3_s3).
    # Evita di pagare l'import a runtime quando non necessario.
    from mypy_boto3_s3.client import S3Client


# -----------------------------------------------------------------------------
# Eccezioni di dominio
# -----------------------------------------------------------------------------
class StorageError(Exception):
    """Errore generico di interazione con object storage."""


class StorageObjectNotFoundError(StorageError):
    """L'oggetto richiesto non esiste nel bucket (404 / NoSuchKey)."""


# -----------------------------------------------------------------------------
# Value object: metadata di un oggetto B2
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    """Subset stabile dei metadati S3 esposti al resto dell'app."""

    content_length: int
    content_type: str


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class B2StorageService:
    """Wrapper S3-compatible con API async di dominio.

    Costruito tipicamente da `from_settings(...)` nel lifespan FastAPI.
    Nei test, si può passare un client moto già configurato.
    """

    def __init__(
        self,
        *,
        client: S3Client,
        bucket: str,
        presign_ttl_seconds: int,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._presign_ttl_seconds = presign_ttl_seconds

    # -------------------------------------------------------------------------
    # Factory da Settings (usato dall'app reale)
    # -------------------------------------------------------------------------
    @classmethod
    def from_settings(cls, settings: Settings) -> B2StorageService:
        """Costruisce un client boto3 puntato a B2 (o qualunque S3-compatible).

        Richiede che le credenziali B2 + bucket + endpoint siano popolati
        in Settings. Per dev senza B2 reale, costruire manualmente con un
        client moto (vedi tests/conftest.py).
        """
        if (
            settings.b2_key_id is None
            or settings.b2_application_key is None
            or settings.b2_bucket_name is None
            or settings.b2_endpoint is None
        ):
            raise StorageError(
                "B2 settings incomplete: key_id, application_key, bucket_name "
                "e endpoint sono tutti richiesti per creare il client."
            )

        # `s3v4` signature richiesta da B2 (e da molti S3-compatible moderni).
        # `addressing_style: path` evita problemi DNS con bucket name con punti.
        client = boto3.client(
            "s3",
            endpoint_url=settings.b2_endpoint,
            aws_access_key_id=settings.b2_key_id.get_secret_value(),
            aws_secret_access_key=settings.b2_application_key.get_secret_value(),
            region_name=settings.b2_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        return cls(
            client=client,
            bucket=settings.b2_bucket_name,
            presign_ttl_seconds=settings.upload_presign_ttl_seconds,
        )

    # -------------------------------------------------------------------------
    # Presigned PUT (init upload)
    # -------------------------------------------------------------------------
    async def generate_presigned_put(
        self,
        key: str,
        *,
        content_type: str,
        content_length: int,
    ) -> tuple[str, datetime]:
        """Genera un URL PUT presigned con vincolo di Content-Length.

        Il client DEVE inviare esattamente `content_length` byte e l'header
        `Content-Type` indicato, altrimenti B2 rifiuta la PUT. Difesa contro
        "size lying" dichiarato in `DocumentInitUpload`.

        Returns:
            tuple (url, expires_at_utc).
        """
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            ClientMethod="put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=self._presign_ttl_seconds,
            HttpMethod="PUT",
        )
        expires_at = datetime.now(UTC) + timedelta(seconds=self._presign_ttl_seconds)
        return url, expires_at

    # -------------------------------------------------------------------------
    # HEAD (verifica esistenza + size + content-type)
    # -------------------------------------------------------------------------
    async def head_object(self, key: str) -> ObjectMetadata:
        """Ritorna ContentLength + ContentType dell'object.

        Raises:
            StorageObjectNotFoundError: 404 / NoSuchKey.
            StorageError: per qualunque altro errore.
        """
        try:
            response = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
        except ClientError as exc:
            self._raise_domain_error(exc, key)

        return ObjectMetadata(
            content_length=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "application/octet-stream")),
        )

    # -------------------------------------------------------------------------
    # GET range (download primi N byte per magic detection)
    # -------------------------------------------------------------------------
    async def get_object_range(self, key: str, *, start: int, end_inclusive: int) -> bytes:
        """Scarica un range di byte dell'object (RFC 7233 Range header).

        Per la validazione MIME server-side ci bastano i primi ~256 byte:
        `await svc.get_object_range(key, start=0, end_inclusive=255)`.

        Args:
            start: offset iniziale (incluso).
            end_inclusive: offset finale (incluso).

        Raises:
            StorageObjectNotFoundError: 404 / NoSuchKey.
            StorageError: altri errori.
        """
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=key,
                Range=f"bytes={start}-{end_inclusive}",
            )
        except ClientError as exc:
            self._raise_domain_error(exc, key)

        # Il body è un StreamingBody di botocore; .read() è sincrono → to_thread.
        body = response["Body"]
        return await asyncio.to_thread(body.read)

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------
    async def delete_object(self, key: str) -> None:
        """Elimina l'object. Idempotente: nessun errore se non esiste.

        S3-compatible: DELETE su key inesistente ritorna 204, non 404.
        Sicuro chiamarlo due volte.
        """
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket,
                Key=key,
            )
        except ClientError as exc:
            # Anche se l'oggetto non c'è, alcuni S3-compatible danno 204 → nessun errore.
            # Però se per qualche motivo solleva, qui mappiamo a domain errors.
            self._raise_domain_error(exc, key)

    # -------------------------------------------------------------------------
    # Helper interno: mappa errori boto3 → domain errors
    # -------------------------------------------------------------------------
    def _raise_domain_error(self, exc: ClientError, key: str) -> None:
        """Centralizza la mappatura ClientError → eccezioni di dominio.

        Sempre solleva (non ritorna): il `return None` annotato è solo per mypy
        — il chiamante può ignorare il valore di ritorno.
        """
        error_code = exc.response.get("Error", {}).get("Code", "")
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        if error_code in {"404", "NoSuchKey", "NoSuchBucket"} or status_code == 404:
            raise StorageObjectNotFoundError(f"Object '{key}' not found in storage") from exc
        raise StorageError(f"Storage error for key '{key}': {error_code}") from exc

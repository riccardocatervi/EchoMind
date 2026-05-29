"""Test del B2StorageService con moto (mock S3 in-memory).

Verifica:
- generate_presigned_put: URL costruito, expires_at coerente, query params attesi
- head_object: ritorna ObjectMetadata corretto
- get_object_range: scarica solo i byte richiesti
- delete_object: rimuove l'object
- Eccezioni di dominio:
    - StorageObjectNotFoundError per HEAD/GET su key inesistente
    - delete idempotente su key inesistente
- from_settings: errore se credenziali incomplete

Niente rete reale: tutto in-memory grazie a `@mock_aws` di moto.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import boto3
import pytest
from moto import mock_aws
from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.services.storage import (
    B2StorageService,
    ObjectMetadata,
    StorageError,
    StorageObjectNotFoundError,
)

TEST_BUCKET = "echomind-test"
TEST_REGION = "us-east-1"  # moto usa us-east-1 di default per S3


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def s3_client() -> Iterator[object]:
    """Client boto3 puntato al mock moto (in-memory)."""
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        yield client


@pytest.fixture
def storage(s3_client: object) -> B2StorageService:
    return B2StorageService(
        client=s3_client,  # type: ignore[arg-type]
        bucket=TEST_BUCKET,
        presign_ttl_seconds=900,
    )


def _put_object(
    client: object, key: str, body: bytes, content_type: str = "application/pdf"
) -> None:
    """Helper: piazza un object nel mock S3."""
    client.put_object(  # type: ignore[attr-defined]
        Bucket=TEST_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


# =============================================================================
# generate_presigned_put
# =============================================================================
class TestGeneratePresignedPut:
    @pytest.mark.asyncio
    async def test_returns_url_with_expected_params(self, storage: B2StorageService) -> None:
        url, _expires_at = await storage.generate_presigned_put(
            "users/abc/file.pdf",
            content_type="application/pdf",
            content_length=1024,
        )
        # URL ben formata: schema, path contiene la key, c'è una query string non vuota.
        # Non testiamo lo schema esatto della firma (X-Amz-* vs AWSAccessKey=*) perché
        # varia con la versione di moto e con la config (anon vs credentials in env).
        parsed = urlparse(url)
        assert parsed.scheme in {"http", "https"}
        assert "users/abc/file.pdf" in parsed.path
        assert parsed.query  # qualche query param di firma è sempre presente

    @pytest.mark.asyncio
    async def test_expires_at_is_in_future(self, storage: B2StorageService) -> None:
        before = datetime.now(UTC)
        _, expires_at = await storage.generate_presigned_put(
            "k", content_type="application/pdf", content_length=10
        )
        delta = expires_at - before
        # TTL configurato a 900s nel fixture
        assert timedelta(seconds=899) <= delta <= timedelta(seconds=901)


# =============================================================================
# head_object
# =============================================================================
class TestHeadObject:
    @pytest.mark.asyncio
    async def test_returns_metadata_for_existing_object(
        self, storage: B2StorageService, s3_client: object
    ) -> None:
        body = b"Hello world" * 10
        _put_object(s3_client, "k1", body, content_type="text/plain")

        meta = await storage.head_object("k1")
        assert isinstance(meta, ObjectMetadata)
        assert meta.content_length == len(body)
        assert meta.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_key(self, storage: B2StorageService) -> None:
        with pytest.raises(StorageObjectNotFoundError):
            await storage.head_object("does-not-exist")


# =============================================================================
# get_object_range
# =============================================================================
class TestGetObjectRange:
    @pytest.mark.asyncio
    async def test_returns_only_requested_bytes(
        self, storage: B2StorageService, s3_client: object
    ) -> None:
        # 1000 byte di payload, chiediamo i primi 256
        body = bytes(range(256)) * 4  # 1024 byte
        _put_object(s3_client, "big", body)

        first_256 = await storage.get_object_range("big", start=0, end_inclusive=255)
        assert len(first_256) == 256
        assert first_256 == body[:256]

    @pytest.mark.asyncio
    async def test_returns_middle_range(self, storage: B2StorageService, s3_client: object) -> None:
        body = b"0123456789ABCDEF"
        _put_object(s3_client, "mid", body)

        chunk = await storage.get_object_range("mid", start=4, end_inclusive=9)
        # bytes=4-9 → 6 byte: "456789"
        assert chunk == b"456789"

    @pytest.mark.asyncio
    async def test_raises_not_found(self, storage: B2StorageService) -> None:
        with pytest.raises(StorageObjectNotFoundError):
            await storage.get_object_range("ghost", start=0, end_inclusive=10)


# =============================================================================
# delete_object
# =============================================================================
class TestDeleteObject:
    @pytest.mark.asyncio
    async def test_removes_existing_object(
        self, storage: B2StorageService, s3_client: object
    ) -> None:
        _put_object(s3_client, "to-delete", b"x")

        # esiste prima della delete
        meta = await storage.head_object("to-delete")
        assert meta.content_length == 1

        await storage.delete_object("to-delete")

        # dopo la delete → not found
        with pytest.raises(StorageObjectNotFoundError):
            await storage.head_object("to-delete")

    @pytest.mark.asyncio
    async def test_delete_is_idempotent_on_missing_key(self, storage: B2StorageService) -> None:
        """S3-compatible: DELETE su key inesistente NON solleva."""
        # Non deve sollevare
        await storage.delete_object("never-existed")

    @pytest.mark.asyncio
    async def test_delete_removes_all_versions_on_versioned_bucket(
        self, storage: B2StorageService, s3_client: object
    ) -> None:
        """Su bucket con versioning, delete_object deve rimuovere TUTTE le versioni.

        Senza il fix version-aware, lascerebbe delete marker + versione storica.
        Con il fix, list_object_versions ritorna 0 dopo la delete.
        """
        # Abilita versioning sul bucket
        s3_client.put_bucket_versioning(  # type: ignore[attr-defined]
            Bucket=TEST_BUCKET,
            VersioningConfiguration={"Status": "Enabled"},
        )

        # Carica 3 versioni successive della STESSA key
        for i in range(3):
            _put_object(s3_client, "versioned-key", f"content-v{i}".encode())

        # Verifica pre-condizione: ci sono 3 versioni
        versions = s3_client.list_object_versions(Bucket=TEST_BUCKET)  # type: ignore[attr-defined]
        assert len(versions.get("Versions", [])) == 3

        # Delete via il nostro service
        await storage.delete_object("versioned-key")

        # Tutte le versioni rimosse + nessun delete marker residuo
        versions = s3_client.list_object_versions(Bucket=TEST_BUCKET)  # type: ignore[attr-defined]
        residual = len(versions.get("Versions", [])) + len(versions.get("DeleteMarkers", []))
        assert residual == 0, f"Attese 0 versioni residue, trovate {residual}"


# =============================================================================
# from_settings: validazione configurazione
# =============================================================================
class TestFromSettings:
    def test_raises_storage_error_when_credentials_missing(self) -> None:
        """Settings dev (B2 vuote) → from_settings rifiuta esplicitamente."""
        settings = Settings.model_construct(
            app_env="development",
            log_level="WARNING",
            database_url="postgresql+asyncpg://u:p@localhost/db",
            supabase_jwt_secret=SecretStr("test-secret-x" * 6),
            supabase_jwt_algorithm="HS256",
            supabase_jwt_audience="authenticated",
            b2_key_id=None,
            b2_application_key=None,
            b2_bucket_name=None,
            b2_endpoint=None,
            b2_region="eu-central-003",
            max_upload_size_bytes=50 * 1024 * 1024,
            upload_presign_ttl_seconds=900,
        )
        with pytest.raises(StorageError, match="B2 settings incomplete"):
            B2StorageService.from_settings(settings)

    def test_creates_client_when_credentials_present(self) -> None:
        """Settings prod-like → costruisce il client senza errori."""
        settings = Settings.model_construct(
            app_env="production",
            log_level="WARNING",
            database_url="postgresql+asyncpg://u:p@localhost/db",
            supabase_jwt_secret=SecretStr("test-secret-x" * 6),
            supabase_jwt_algorithm="HS256",
            supabase_jwt_audience="authenticated",
            b2_key_id=SecretStr("ci-dummy-key-id"),
            b2_application_key=SecretStr("ci-dummy-app-key"),
            b2_bucket_name="echomind-staging",
            b2_endpoint="https://s3.eu-central-003.backblazeb2.com",
            b2_region="eu-central-003",
            max_upload_size_bytes=50 * 1024 * 1024,
            upload_presign_ttl_seconds=900,
        )
        svc = B2StorageService.from_settings(settings)
        assert svc is not None

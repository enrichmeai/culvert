"""GcsBlobStore — BlobStore Protocol over google-cloud-storage.

Java sibling: ``com.enrichmeai.culvert.gcp.gcs.GcsBlobStore``.
"""

from __future__ import annotations

import io
import logging
from typing import Any, BinaryIO, Iterator
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class GcsBlobStore:
    """BlobStore implementation backed by Google Cloud Storage.

    Accepts ``gs://bucket/path`` URIs; rejects foreign schemes with
    ``ValueError`` (cloud-neutral consumers should not be passing
    ``s3://`` URIs to a GCS adapter).
    """

    SCHEME = "gs"

    def __init__(self, client: Any) -> None:
        if client is None:
            raise TypeError("client must not be None")
        self.client = client

    # --- BlobStore Protocol ----------------------------------------------

    def get(self, uri: str) -> bytes:
        bucket_name, blob_name = self._parse(uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            return blob.download_as_bytes()
        except Exception as exc:
            if self._is_not_found(exc):
                raise FileNotFoundError(uri) from exc
            raise

    def open(self, uri: str, mode: str = "rb") -> BinaryIO:
        bucket_name, blob_name = self._parse(uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if mode in ("rb", "r"):
            # Buffer the bytes in memory for the simple-case open.
            # Large-object callers should use blob.open(mode='rb') directly.
            return io.BytesIO(blob.download_as_bytes())
        if mode in ("wb", "w"):
            return blob.open(mode="wb")
        raise ValueError(f"Unsupported mode: {mode}")

    def put(self, uri: str, data: bytes) -> None:
        bucket_name, blob_name = self._parse(uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data)

    def list(self, prefix: str) -> Iterator[str]:
        bucket_name, blob_prefix = self._parse(prefix, allow_dir=True)
        for blob in self.client.list_blobs(bucket_name, prefix=blob_prefix):
            yield f"gs://{bucket_name}/{blob.name}"

    def exists(self, uri: str) -> bool:
        bucket_name, blob_name = self._parse(uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return bool(blob.exists())

    def delete(self, uri: str) -> None:
        bucket_name, blob_name = self._parse(uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            blob.delete()
        except Exception as exc:
            if self._is_not_found(exc):
                # Idempotent: deleting a missing object is fine.
                return
            raise

    # --- helpers ----------------------------------------------------------

    @classmethod
    def _parse(cls, uri: str, allow_dir: bool = False) -> tuple[str, str]:
        if uri is None:
            raise TypeError("uri must not be None")
        parsed = urlparse(uri)
        if parsed.scheme != cls.SCHEME:
            raise ValueError(
                f"GcsBlobStore only accepts gs:// URIs, got {uri!r}"
            )
        if not parsed.netloc:
            raise ValueError(f"URI missing bucket: {uri!r}")
        blob_name = parsed.path.lstrip("/")
        if not blob_name and not allow_dir:
            raise ValueError(f"URI missing object path: {uri!r}")
        return parsed.netloc, blob_name

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        # google.api_core.exceptions.NotFound has code=404; we duck-type
        # rather than import the GCP exception so this stays loosely
        # coupled to the SDK version.
        return getattr(exc, "code", None) == 404 or "404" in str(exc) or "not found" in str(exc).lower()

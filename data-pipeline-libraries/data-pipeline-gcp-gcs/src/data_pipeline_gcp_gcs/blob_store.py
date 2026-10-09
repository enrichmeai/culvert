"""GcsBlobStore — BlobStore Protocol over google-cloud-storage.

Java sibling: ``com.enrichmeai.culvert.gcp.gcs.GcsBlobStore``.
"""

from __future__ import annotations

import logging
from typing import Any, BinaryIO, Iterator
from urllib.parse import urlparse

from data_pipeline_core.contracts.blob_store import BlobMetadata

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

    def open_input(self, uri: str) -> BinaryIO:
        """Stream the object at `uri`, a chunk at a time.

        One metadata GET first: it turns a missing object into
        ``FileNotFoundError`` here, as the contract asks, rather than at the
        first read, and it records the object's generation. Every ranged read
        is then pinned to that generation (``if_generation_match``), so an
        object replaced while it is being read fails loudly (HTTP 412) rather
        than mixing two versions in one stream.
        """
        bucket_name, blob_name = self._parse(uri)
        blob = self.client.bucket(bucket_name).blob(blob_name)
        try:
            blob.reload()
        except Exception as exc:
            if self._is_not_found(exc):
                raise FileNotFoundError(uri) from exc
            raise
        if blob.generation is None:
            # if_generation_match=None would silently turn the pin off.
            raise RuntimeError(f"GCS reported no generation for {uri}; refusing an unpinned read")
        return blob.open("rb", if_generation_match=blob.generation)

    def open_output(self, uri: str) -> BinaryIO:
        """A streaming (resumable) upload to `uri`.

        Closing it commits the object; an exception inside ``with`` cancels the
        upload, and nothing is written.
        """
        bucket_name, blob_name = self._parse(uri)
        return self.client.bucket(bucket_name).blob(blob_name).open("wb")

    def open(self, uri: str, mode: str = "rb") -> BinaryIO:
        """Deprecated: kept for callers from before ``open_input``/``open_output``.

        ``"rb"`` now streams (``open_input``); ``"wb"`` is ``open_output``.
        """
        if mode in ("rb", "r"):
            return self.open_input(uri)
        if mode in ("wb", "w"):
            return self.open_output(uri)
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

    def head(self, uri: str) -> BlobMetadata:
        """Describe the object at `uri` from one metadata GET, without its bytes.

        ``Bucket.get_blob`` reloads the object's metadata only, and returns
        None for a missing object. GCS reports an ETag on every object, so a
        None here is a mocked or degraded client: it becomes ``""`` rather
        than a TypeError further on. A removed custom-metadata key (a None
        value) is dropped.
        """
        bucket_name, blob_name = self._parse(uri)
        blob = self.client.bucket(bucket_name).get_blob(blob_name)
        if blob is None:
            raise FileNotFoundError(uri)
        metadata = {
            k: v for k, v in (blob.metadata or {}).items() if k is not None and v is not None
        }
        return BlobMetadata(
            uri=uri,
            size=int(blob.size or 0),
            etag=blob.etag or "",
            last_modified=blob.updated,
            metadata=metadata,
        )

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

    def copy(self, src: str, dst: str) -> None:
        """Server-side copy from `src` to `dst`; no bytes leave GCS.

        Raises FileNotFoundError if `src` does not exist (GCS reports a missing
        destination bucket the same way), and NotImplementedError for a
        destination outside GCS.
        """
        if dst is not None and urlparse(dst).scheme != self.SCHEME:
            raise NotImplementedError(f"GcsBlobStore copies within GCS only, not to {dst!r}")
        src_bucket_name, src_name = self._parse(src)
        dst_bucket_name, dst_name = self._parse(dst)
        src_bucket = self.client.bucket(src_bucket_name)
        try:
            src_bucket.copy_blob(src_bucket.blob(src_name), self.client.bucket(dst_bucket_name),
                                 new_name=dst_name)
        except Exception as exc:
            if self._is_not_found(exc):
                raise FileNotFoundError(src) from exc
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

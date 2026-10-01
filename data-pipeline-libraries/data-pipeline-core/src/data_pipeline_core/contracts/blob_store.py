"""BlobStore — object storage abstraction.

URIs are opaque strings (`gs://`, `s3://`, `abfs://`). The framework
does not parse them; implementations do. Callers that need to inspect
a blob take a `BlobStore` dependency and ask it directly — no
scheme-sniffing in framework code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import BinaryIO, Iterator, Mapping, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class BlobMetadata:
    """What `BlobStore.head` reports about an object, without its bytes.

    Java mirror: ``com.enrichmeai.culvert.contracts.BlobMetadata``. No field is
    ever None except `last_modified`: `etag` is `""` for a store that reports
    no version token, and `metadata` is an empty mapping when there is none.
    `metadata` is read-only.
    """

    uri: str
    size: int
    etag: str
    last_modified: Optional[datetime] = None
    # Left out of the hash (a read-only mapping is unhashable), so a
    # BlobMetadata can still key a dict or sit in a set, as Java's record can.
    metadata: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if self.uri is None:
            raise TypeError("uri must not be None")
        if self.etag is None:
            raise TypeError(
                "etag must not be None: pass an empty string for a store that reports none"
            )
        if self.metadata is None:
            raise TypeError("metadata must not be None: pass an empty mapping")
        if self.size < 0:
            raise ValueError(f"size must not be negative: {self.size}")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@runtime_checkable
class BlobStore(Protocol):
    """Object storage abstraction. Cloud-neutral by construction.

    Implementations should treat URIs as opaque (they parse them
    internally) and should raise `FileNotFoundError` for `get`/`open`
    against a missing object, matching Python's filesystem idioms.
    """

    def get(self, uri: str) -> bytes:
        """Return the full object bytes at `uri`.

        Raises FileNotFoundError if the object does not exist.
        """
        ...

    def open_input(self, uri: str) -> BinaryIO:
        """Open a streaming read handle on the object at `uri`.

        Use for large objects where loading the full bytes into memory
        is wasteful. Callers must close the stream (use as a context
        manager where possible).

        Raises FileNotFoundError if the object does not exist.
        """
        ...

    def open_output(self, uri: str) -> BinaryIO:
        """Open a streaming write handle for the object at `uri`.

        Callers must close the stream to commit the write (use as a
        context manager where possible). Overwrites existing objects.
        """
        ...

    def put(self, uri: str, data: bytes) -> None:
        """Write `data` to `uri`. Overwrites existing objects."""
        ...

    def list(self, prefix: str) -> Iterator[str]:
        """Yield object URIs under `prefix`, lexicographic order.

        `prefix` is itself a URI (e.g. `gs://bucket/dir/`). The yielded
        URIs are absolute.
        """
        ...

    def exists(self, uri: str) -> bool:
        """Return True if an object exists at `uri`."""
        ...

    def head(self, uri: str) -> BlobMetadata:
        """Describe the object at `uri` without reading it.

        Returns its size, the store's version token (ETag), last-modified time
        and custom metadata. The version token is the point: a loader that
        must be idempotent keys on `(uri, etag)`, so an object already loaded
        at that ETag is skipped and a republished one is loaded as new.
        `list` and `exists` cannot answer that, and reading the object to find
        out costs the bytes the question exists to avoid.

        Raises FileNotFoundError if the object does not exist, as `get` does.
        """
        ...

    def delete(self, uri: str) -> None:
        """Delete the object at `uri`.

        Idempotent: deleting a missing object is not an error.
        """
        ...

    def copy(self, src: str, dst: str) -> None:
        """Server-side copy from `src` to `dst`.

        Within the same store this should be a metadata-only operation
        (no bytes leave the cloud). Cross-store copies (`gs://` to
        `s3://`) are out of scope; implementations may raise
        `NotImplementedError` for foreign schemes.
        """
        ...

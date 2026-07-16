"""BlobStore — object storage abstraction.

URIs are opaque strings (`gs://`, `s3://`, `abfs://`). The framework
does not parse them; implementations do. Callers that need to inspect
a blob take a `BlobStore` dependency and ask it directly — no
scheme-sniffing in framework code.
"""

from __future__ import annotations

from typing import BinaryIO, Iterator, Protocol, runtime_checkable


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

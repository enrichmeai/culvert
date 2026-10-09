"""BlobStore contract test mixin.

Java mirror: ``com.enrichmeai.culvert.contracttests.BlobStoreContractTest``
"""

from __future__ import annotations

import pytest


class BlobStoreContract:
    """Mixin — subclasses provide ``store``, ``known_uri``, ``missing_uri``
    fixtures. ``known_uri`` resolves to bytes equal to ``b"hello"``.

    Java mirror: ``BlobStoreContractTest`` (Sprint-5 deliverable). The
    protocol-completeness and ``open_input`` tests are Python-only so far: a
    Python store can be bound without implementing every method, which is how
    ``GcsBlobStore`` came to lack ``open_input``/``open_output``/``copy``.
    """

    def test_it_implements_every_blob_store_method(self, store):
        from data_pipeline_core.contracts.blob_store import BlobStore
        missing = [m for m in ("get", "open_input", "open_output", "put", "list", "exists",
                               "head", "delete", "copy") if not callable(getattr(store, m, None))]
        assert not missing, f"{type(store).__name__} lacks {missing}"
        assert isinstance(store, BlobStore)

    def test_open_input_known_streams_the_bytes(self, store, known_uri):
        with store.open_input(known_uri) as stream:
            assert stream.read() == b"hello"

    def test_open_input_missing_fails_as_get_does(self, store, missing_uri):
        with pytest.raises(FileNotFoundError):
            store.open_input(missing_uri)

    def test_get_known_returns_bytes(self, store, known_uri):
        assert store.get(known_uri) == b"hello"

    def test_exists_known_true(self, store, known_uri):
        assert store.exists(known_uri) is True

    def test_exists_missing_false(self, store, missing_uri):
        assert store.exists(missing_uri) is False

    def test_head_known_describes_the_object_without_reading_it(self, store, known_uri):
        # Java: ``headKnownDescribesTheObjectWithoutReadingIt``. A binding
        # whose fake client must be told the metadata stubs size and ETag for
        # the known object: a fake reporting no ETag would make a loader keyed
        # on (uri, etag) skip nothing and load everything twice.
        metadata = store.head(known_uri)
        assert metadata.uri == known_uri
        assert metadata.size == len(b"hello")
        assert metadata.etag.strip(), "the store's version token must not be blank"
        assert metadata.last_modified is not None
        assert metadata.metadata is not None

    def test_head_missing_fails_as_get_does(self, store, missing_uri):
        # Java: ``headMissingFailsAsGetDoes``: not None, not an empty description.
        with pytest.raises(FileNotFoundError):
            store.head(missing_uri)

    def test_delete_missing_idempotent(self, store, missing_uri):
        # Should not raise.
        store.delete(missing_uri)

    def test_null_arguments_rejected(self, store):
        # Java: ``nullArgumentsRejected`` — get(null) must raise.
        with pytest.raises((TypeError, ValueError)):
            store.get(None)

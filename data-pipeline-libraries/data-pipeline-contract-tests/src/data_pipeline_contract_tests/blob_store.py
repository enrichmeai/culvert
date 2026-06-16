"""BlobStore contract test mixin.

Java mirror: ``com.enrichmeai.culvert.contracttests.BlobStoreContractTest``
"""

from __future__ import annotations

import pytest


class BlobStoreContract:
    """Mixin — subclasses provide ``store``, ``known_uri``, ``missing_uri``
    fixtures. ``known_uri`` resolves to bytes equal to ``b"hello"``.

    Java mirror: ``BlobStoreContractTest`` (Sprint-5 deliverable).
    """

    def test_get_known_returns_bytes(self, store, known_uri):
        assert store.get(known_uri) == b"hello"

    def test_exists_known_true(self, store, known_uri):
        assert store.exists(known_uri) is True

    def test_exists_missing_false(self, store, missing_uri):
        assert store.exists(missing_uri) is False

    def test_delete_missing_idempotent(self, store, missing_uri):
        # Should not raise.
        store.delete(missing_uri)

    def test_null_arguments_rejected(self, store):
        # Java: ``nullArgumentsRejected`` — get(null) must raise.
        with pytest.raises((TypeError, ValueError)):
            store.get(None)

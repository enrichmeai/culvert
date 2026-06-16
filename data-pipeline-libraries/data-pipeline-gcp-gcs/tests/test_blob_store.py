"""Tests for GcsBlobStore — no real GCS."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_contract_tests import BlobStoreContract
from data_pipeline_gcp_gcs import GcsBlobStore


@pytest.fixture
def mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# Contract tests — bind BlobStoreContract to GcsBlobStore
# ---------------------------------------------------------------------------

class TestGcsBlobStoreContract(BlobStoreContract):
    """Exercise every BlobStoreContract guarantee against a mocked GCS client.

    The mixin requires three fixtures:
      ``store``      — a GcsBlobStore instance
      ``known_uri``  — a URI whose content is exactly ``b"hello"``
      ``missing_uri``— a URI that does not exist
    """

    @pytest.fixture
    def store(self):
        """GcsBlobStore backed by a MagicMock client keyed on blob name."""
        client = MagicMock()

        def _bucket_factory(bucket_name):
            bucket = MagicMock()

            def _blob_factory(blob_name):
                blob = MagicMock()
                if blob_name == "path/known":
                    blob.download_as_bytes.return_value = b"hello"
                    blob.exists.return_value = True
                else:
                    # missing blob: download raises 404, exists returns False
                    not_found = Exception("404 not found")
                    not_found.code = 404
                    blob.download_as_bytes.side_effect = not_found
                    blob.exists.return_value = False
                    # delete is idempotent — raise a 404 that the adapter swallows
                    delete_err = Exception("not found")
                    delete_err.code = 404
                    blob.delete.side_effect = delete_err
                return blob

            bucket.blob.side_effect = _blob_factory
            return bucket

        client.bucket.side_effect = _bucket_factory
        return GcsBlobStore(client)

    @pytest.fixture
    def known_uri(self):
        return "gs://test-bucket/path/known"

    @pytest.fixture
    def missing_uri(self):
        return "gs://test-bucket/path/missing"


def test_constructor_rejects_none():
    with pytest.raises(TypeError):
        GcsBlobStore(None)


def test_get_returns_bytes(mock_client):
    blob = MagicMock()
    blob.download_as_bytes.return_value = b"hello"
    mock_client.bucket.return_value.blob.return_value = blob

    store = GcsBlobStore(mock_client)
    assert store.get("gs://my-bucket/path/to/file") == b"hello"


def test_get_raises_filenotfound_on_404(mock_client):
    blob = MagicMock()
    err = Exception("404 not found")
    err.code = 404
    blob.download_as_bytes.side_effect = err
    mock_client.bucket.return_value.blob.return_value = blob

    store = GcsBlobStore(mock_client)
    with pytest.raises(FileNotFoundError):
        store.get("gs://my-bucket/missing")


def test_put_uploads_bytes(mock_client):
    blob = MagicMock()
    mock_client.bucket.return_value.blob.return_value = blob

    store = GcsBlobStore(mock_client)
    store.put("gs://my-bucket/dest", b"payload")

    blob.upload_from_string.assert_called_once_with(b"payload")


def test_list_yields_gs_uris(mock_client):
    blob1 = MagicMock()
    blob1.name = "dir/a"
    blob2 = MagicMock()
    blob2.name = "dir/b"
    mock_client.list_blobs.return_value = [blob1, blob2]

    store = GcsBlobStore(mock_client)
    uris = list(store.list("gs://my-bucket/dir/"))

    assert uris == ["gs://my-bucket/dir/a", "gs://my-bucket/dir/b"]


def test_exists_true(mock_client):
    mock_client.bucket.return_value.blob.return_value.exists.return_value = True
    store = GcsBlobStore(mock_client)
    assert store.exists("gs://my-bucket/file") is True


def test_exists_false(mock_client):
    mock_client.bucket.return_value.blob.return_value.exists.return_value = False
    store = GcsBlobStore(mock_client)
    assert store.exists("gs://my-bucket/missing") is False


def test_delete_idempotent_on_404(mock_client):
    blob = MagicMock()
    err = Exception("not found")
    err.code = 404
    blob.delete.side_effect = err
    mock_client.bucket.return_value.blob.return_value = blob

    store = GcsBlobStore(mock_client)
    # Should not raise
    store.delete("gs://my-bucket/missing")


def test_delete_propagates_other_errors(mock_client):
    blob = MagicMock()
    err = Exception("permission denied")
    err.code = 403
    blob.delete.side_effect = err
    mock_client.bucket.return_value.blob.return_value = blob

    store = GcsBlobStore(mock_client)
    with pytest.raises(Exception):
        store.delete("gs://my-bucket/forbidden")


def test_rejects_s3_uri(mock_client):
    store = GcsBlobStore(mock_client)
    with pytest.raises(ValueError):
        store.get("s3://bucket/file")


def test_rejects_missing_bucket(mock_client):
    store = GcsBlobStore(mock_client)
    with pytest.raises(ValueError):
        store.get("gs:///file")


def test_rejects_missing_object(mock_client):
    store = GcsBlobStore(mock_client)
    with pytest.raises(ValueError):
        store.get("gs://bucket/")

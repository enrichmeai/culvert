"""Tests for GcsBlobStore — no real GCS."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_gcp_gcs import GcsBlobStore


@pytest.fixture
def mock_client():
    return MagicMock()


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

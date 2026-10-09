"""Tests for GcsBlobStore — no real GCS."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from google.cloud.storage.fileio import BlobReader

from data_pipeline_contract_tests import BlobStoreContract
from data_pipeline_gcp_gcs import GcsBlobStore


class FakeBlob:
    """A blob with real GCS read semantics where they matter: ranged downloads, the
    generation precondition, and ``open("rb")`` returning the library's own BlobReader."""

    def __init__(self, data=None, generation=7, chunk_size=None):
        self.data = data
        self.generation = None
        self._generation = generation
        self.chunk_size = chunk_size
        self.ranges = []

    def reload(self):
        if self.data is None:
            err = Exception("404 Not Found")
            err.code = 404
            raise err
        self.generation = self._generation

    def _not_found(self):
        err = Exception("404 Not Found")
        err.code = 404
        return err

    def exists(self):
        return self.data is not None

    def delete(self):
        if self.data is None:
            raise self._not_found()
        self.data = None

    def download_as_bytes(self, start=None, end=None, checksum=None, retry=None,
                          if_generation_match=None, **kwargs):
        if self.data is None:
            raise self._not_found()
        if if_generation_match is not None and if_generation_match != self._generation:
            err = Exception("412 Precondition Failed")
            err.code = 412
            raise err
        self.ranges.append((start, end))
        return self.data[start or 0:None if end is None else end + 1]

    def open(self, mode="rb", **kwargs):
        assert mode == "rb"
        return BlobReader(self, **kwargs)


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
                return FakeBlob(b"hello" if blob_name == "path/known" else None)

            def _get_blob(blob_name):
                # What a real object reports on a metadata GET (no content).
                if blob_name != "path/known":
                    return None
                blob = MagicMock()
                blob.size = 5
                blob.etag = "CJDE7Zr5y4kDEAE="
                blob.updated = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
                blob.metadata = {"source": "contract"}
                return blob

            bucket.blob.side_effect = _blob_factory
            bucket.get_blob.side_effect = _get_blob
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


# --- head -----------------------------------------------------------------


def _stub_get_blob(client, blob):
    client.bucket.return_value.get_blob.return_value = blob


def test_head_reads_metadata_not_content(mock_client):
    blob = MagicMock()
    blob.size = 42
    blob.etag = "CJDE7Zr5y4kDEAE="
    blob.updated = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    blob.metadata = {"source": "crm"}
    _stub_get_blob(mock_client, blob)

    meta = GcsBlobStore(mock_client).head("gs://b/landing/customers.csv")

    assert meta.uri == "gs://b/landing/customers.csv"
    assert meta.size == 42
    assert meta.etag == "CJDE7Zr5y4kDEAE="
    assert meta.last_modified == datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    assert dict(meta.metadata) == {"source": "crm"}
    mock_client.bucket.assert_called_once_with("b")
    mock_client.bucket.return_value.get_blob.assert_called_once_with("landing/customers.csv")
    blob.download_as_bytes.assert_not_called()


def test_head_missing_object_raises_file_not_found(mock_client):
    _stub_get_blob(mock_client, None)
    with pytest.raises(FileNotFoundError, match="gs://b/missing"):
        GcsBlobStore(mock_client).head("gs://b/missing")


def test_head_turns_a_missing_etag_into_empty_string_and_drops_removed_keys(mock_client):
    blob = MagicMock()
    blob.size = None
    blob.etag = None
    blob.updated = None
    blob.metadata = {"kept": "yes", "removed": None}
    _stub_get_blob(mock_client, blob)

    meta = GcsBlobStore(mock_client).head("gs://b/x")

    assert meta.etag == ""
    assert meta.size == 0
    assert meta.last_modified is None
    assert dict(meta.metadata) == {"kept": "yes"}


def test_head_metadata_is_read_only(mock_client):
    blob = MagicMock()
    blob.size, blob.etag, blob.updated, blob.metadata = 1, "e", None, None
    _stub_get_blob(mock_client, blob)

    meta = GcsBlobStore(mock_client).head("gs://b/x")

    assert dict(meta.metadata) == {}
    with pytest.raises(TypeError):
        meta.metadata["k"] = "v"


def test_head_rejects_none_uri(mock_client):
    with pytest.raises(TypeError):
        GcsBlobStore(mock_client).head(None)


# ---------------------------------------------------------------------------
# Streaming read, write and copy (the BlobStore methods GcsBlobStore lacked)
# ---------------------------------------------------------------------------

def _store_with(blob, bucket_name="b"):
    client = MagicMock()
    client.bucket.return_value.blob.return_value = blob
    client.bucket.return_value.name = bucket_name
    return GcsBlobStore(client), client


def test_open_input_streams_in_ranged_reads_pinned_to_the_generation():
    blob = FakeBlob(b"0123456789" * 10, generation=42, chunk_size=256 * 1024)
    store, _ = _store_with(blob)
    with store.open_input("gs://b/big") as stream:
        assert stream.read(10) == b"0123456789"
        assert stream.read() == b"0123456789" * 9
    assert blob.ranges, "the bytes came from ranged downloads"
    assert blob.ranges[0][0] == 0


def test_open_input_reads_only_what_is_asked_for():
    blob = FakeBlob(b"x" * 1_000_000, chunk_size=262144)
    store, _ = _store_with(blob)
    with store.open_input("gs://b/big") as stream:
        stream.read(100)
    (start, end), = blob.ranges
    assert start == 0 and end < 300_000, "one chunk, not the whole object"


def test_an_object_replaced_mid_read_fails_rather_than_mixing_versions():
    blob = FakeBlob(b"a" * 600_000, generation=1, chunk_size=262144)
    store, _ = _store_with(blob)
    stream = store.open_input("gs://b/obj")
    stream.read(10)
    blob._generation = 2  # someone republished the object
    with pytest.raises(Exception, match="412"):
        stream.read()


def test_open_input_missing_raises_file_not_found_at_open():
    store, _ = _store_with(FakeBlob(None))
    with pytest.raises(FileNotFoundError, match="gs://b/missing"):
        store.open_input("gs://b/missing")


def test_open_output_is_the_blobs_writer():
    blob = MagicMock()
    store, _ = _store_with(blob)
    assert store.open_output("gs://b/out") is blob.open.return_value
    blob.open.assert_called_once_with("wb")


def test_the_old_open_delegates_and_now_streams():
    blob = FakeBlob(b"hello")
    store, _ = _store_with(blob)
    with store.open("gs://b/x") as stream:
        assert stream.read() == b"hello"
    with pytest.raises(ValueError, match="Unsupported mode"):
        store.open("gs://b/x", "a")


def test_copy_is_server_side_within_gcs():
    client = MagicMock()
    src_bucket, dst_bucket = MagicMock(), MagicMock()
    client.bucket.side_effect = lambda name: {"src": src_bucket, "dst": dst_bucket}[name]
    GcsBlobStore(client).copy("gs://src/a/1.json", "gs://dst/b/1.json")
    src_bucket.copy_blob.assert_called_once_with(
        src_bucket.blob.return_value, dst_bucket, new_name="b/1.json")
    src_bucket.blob.assert_called_once_with("a/1.json")


def test_copy_of_a_missing_object_raises_file_not_found(mock_client):
    err = Exception("404 Not Found")
    err.code = 404
    mock_client.bucket.return_value.copy_blob.side_effect = err
    with pytest.raises(FileNotFoundError, match="gs://b/missing"):
        GcsBlobStore(mock_client).copy("gs://b/missing", "gs://b/new")


def test_copy_outside_gcs_is_not_implemented(mock_client):
    with pytest.raises(NotImplementedError, match="within GCS only"):
        GcsBlobStore(mock_client).copy("gs://b/a", "s3://other/a")


def test_blob_lines_source_over_gcs_now_streams():
    """#13's BlobLinesSource reads GCS through open_input: ranged reads, not one download."""
    from data_pipeline_core import BlobLinesSource
    lines = b"".join(b'{"n": %d}\n' % i for i in range(50_000))
    blob = FakeBlob(lines, chunk_size=262144)
    store, _ = _store_with(blob)
    records = list(BlobLinesSource("gs://b/orders.jsonl", store).read(None))
    assert len(records) == 50_000 and records[-1] == {"n": 49_999}
    assert len(blob.ranges) > 1 and all(end is not None for _, end in blob.ranges[:-1])


def test_a_read_with_no_generation_is_refused_rather_than_left_unpinned():
    blob = FakeBlob(b"hello")
    blob.reload = lambda: None  # a reload that reports no generation
    store, _ = _store_with(blob)
    with pytest.raises(RuntimeError, match="no generation"):
        store.open_input("gs://b/x")

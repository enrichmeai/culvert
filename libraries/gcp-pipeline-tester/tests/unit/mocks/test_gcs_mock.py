"""Unit tests for mocks/gcs_mock.py - GCS mock classes."""

import unittest

from gcp_pipeline_tester.mocks.gcs_mock import GCSClientMock, GCSBucketMock


class TestGCSClientMock(unittest.TestCase):
    """Tests for GCSClientMock class."""

    def test_init(self):
        """Test GCSClientMock initialization."""
        mock = GCSClientMock()

        self.assertEqual(mock.files, {})
        self.assertEqual(mock.written_files, {})

    def test_write_file_stores_content(self):
        """Test write_file stores content for reading."""
        mock = GCSClientMock()

        mock.write_file("gs://bucket/test.txt", "Hello, World!")

        self.assertEqual(mock.files["gs://bucket/test.txt"], "Hello, World!")

    def test_open_read_mode(self):
        """Test open in read mode returns file content."""
        mock = GCSClientMock()
        mock.write_file("gs://bucket/test.txt", "Test content")

        with mock.open("gs://bucket/test.txt", "r") as f:
            content = f.read()

        self.assertEqual(content, "Test content")

    def test_open_read_mode_empty_file(self):
        """Test open read mode for non-existent file returns empty."""
        mock = GCSClientMock()

        with mock.open("gs://bucket/missing.txt", "r") as f:
            content = f.read()

        self.assertEqual(content, "")

    def test_open_write_mode(self):
        """Test open in write mode stores content."""
        mock = GCSClientMock()

        with mock.open("gs://bucket/output.txt", "w") as f:
            f.write("Output content")

        self.assertEqual(mock.written_files["gs://bucket/output.txt"], "Output content")

    def test_get_written_files(self):
        """Test get_written_files returns copy of written files."""
        mock = GCSClientMock()

        with mock.open("gs://bucket/file1.txt", "w") as f:
            f.write("Content 1")
        with mock.open("gs://bucket/file2.txt", "w") as f:
            f.write("Content 2")

        written = mock.get_written_files()

        self.assertEqual(len(written), 2)
        self.assertEqual(written["gs://bucket/file1.txt"], "Content 1")
        self.assertEqual(written["gs://bucket/file2.txt"], "Content 2")

    def test_get_written_files_returns_copy(self):
        """Test get_written_files returns a copy, not the original."""
        mock = GCSClientMock()

        with mock.open("gs://bucket/file.txt", "w") as f:
            f.write("Content")

        written = mock.get_written_files()
        written["new_key"] = "new_value"

        # Original should be unchanged
        self.assertNotIn("new_key", mock.written_files)


class TestGCSBucketMock(unittest.TestCase):
    """Tests for GCSBucketMock class."""

    def test_init(self):
        """Test GCSBucketMock initialization."""
        bucket = GCSBucketMock("my-bucket")

        self.assertEqual(bucket.name, "my-bucket")
        self.assertEqual(bucket.blobs, {})

    def test_upload_file(self):
        """Test upload_file stores blob info."""
        bucket = GCSBucketMock("my-bucket")

        bucket.upload_file("local/file.txt", "remote/file.txt")

        self.assertIn("remote/file.txt", bucket.blobs)
        self.assertEqual(bucket.blobs["remote/file.txt"]["local_path"], "local/file.txt")

    def test_list_blobs(self):
        """Test list_blobs returns all blobs."""
        bucket = GCSBucketMock("my-bucket")

        bucket.upload_file("file1.txt", "blob1.txt")
        bucket.upload_file("file2.txt", "blob2.txt")

        blobs = bucket.list_blobs()

        self.assertEqual(len(blobs), 2)
        self.assertIn("blob1.txt", blobs)
        self.assertIn("blob2.txt", blobs)

    def test_list_blobs_returns_copy(self):
        """Test list_blobs returns copy of blobs."""
        bucket = GCSBucketMock("my-bucket")
        bucket.upload_file("file.txt", "blob.txt")

        blobs = bucket.list_blobs()
        blobs["new_blob"] = {}

        # Original should be unchanged
        self.assertNotIn("new_blob", bucket.blobs)

    def test_download_file_does_not_raise(self):
        """Test download_file completes without error."""
        bucket = GCSBucketMock("my-bucket")

        # Should not raise
        bucket.download_file("remote/file.txt", "local/file.txt")


if __name__ == "__main__":
    unittest.main()


"""
GCS Mock Module

Mock objects for Google Cloud Storage testing.
"""

from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock


class GCSClientMock:
    """
    Mock GCS client for testing.

    Provides a mock interface for GCS operations without
    requiring actual GCS connectivity.

    Example:
        >>> mock_client = GCSClientMock()
        >>> with mock_client.open('gs://bucket/file.txt', 'r') as f:
        ...     content = f.read()
    """

    def __init__(self):
        """Initialize mock GCS client."""
        self.files: Dict[str, str] = {}
        self.written_files: Dict[str, str] = {}

    def open(self, path: str, mode: str = 'r'):
        """
        Mock file opening.

        Args:
            path: GCS file path
            mode: File mode ('r' or 'w')

        Returns:
            Mock file object
        """
        if mode == 'r':
            content = self.files.get(path, '')
            return MagicMock(
                __enter__=lambda self: MagicMock(read=lambda: content),
                __exit__=MagicMock(return_value=None)
            )
        elif mode == 'w':
            mock_file = MagicMock()
            mock_file.write = lambda content: self.written_files.update({path: content})
            return MagicMock(
                __enter__=lambda self: mock_file,
                __exit__=MagicMock(return_value=None)
            )

    def write_file(self, path: str, content: str) -> None:
        """Write file content for reading."""
        self.files[path] = content

    def get_written_files(self) -> Dict[str, str]:
        """Get all files written during test."""
        return self.written_files.copy()


class GCSBucketMock:
    """
    Mock GCS bucket for testing.

    Simulates bucket operations without actual GCS connectivity.

    Example:
        >>> bucket = GCSBucketMock('my-bucket')
        >>> bucket.upload_file('local.txt', 'remote.txt')
    """

    def __init__(self, name: str):
        """
        Initialize mock bucket.

        Args:
            name: Bucket name
        """
        self.name = name
        self.blobs: Dict[str, Any] = {}

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Mock file upload."""
        self.blobs[remote_path] = {'local_path': local_path}

    def download_file(self, remote_path: str, local_path: str) -> None:
        """Mock file download."""
        pass

    def list_blobs(self) -> Dict[str, Any]:
        """Get all blobs in bucket."""
        return self.blobs.copy()


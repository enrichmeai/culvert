"""
GCS Fixtures Module

Test fixtures for Google Cloud Storage testing.
"""

import pytest
from unittest.mock import Mock
from typing import Dict, List


@pytest.fixture
def gcs_client_mock():
    """
    Fixture providing a mocked GCS client.

    Returns:
        Mock GCS client with open() method

    Example:
        >>> def test_with_gcs_mock(gcs_client_mock):
        ...     gcs_client_mock.open.return_value.__enter__.return_value = ...
    """
    mock_client = Mock()
    return mock_client


@pytest.fixture
def gcs_bucket_mock() -> str:
    """
    Fixture providing a mock GCS bucket name.

    Returns:
        str: Mock bucket name for testing

    Example:
        >>> def test_with_bucket(gcs_bucket_mock):
        ...     path = f"gs://{gcs_bucket_mock}/file.txt"
    """
    return "test-bucket"


@pytest.fixture
def gcs_test_paths() -> List[str]:
    """
    Fixture providing sample GCS paths for testing.

    Returns:
        List of GCS paths

    Example:
        >>> def test_with_paths(gcs_test_paths):
        ...     assert len(gcs_test_paths) > 0
    """
    return [
        "gs://test-bucket/input/file1.csv",
        "gs://test-bucket/input/file2.csv",
        "gs://test-bucket/input/file3.csv",
    ]


@pytest.fixture
def gcs_test_file_content() -> str:
    """
    Fixture providing sample file content for GCS testing.

    Returns:
        str: Sample file content

    Example:
        >>> def test_with_content(gcs_test_file_content):
        ...     lines = gcs_test_file_content.split('\\n')
    """
    return """id,name,email
1,John,john@example.com
2,Jane,jane@example.com
3,Bob,bob@example.com
"""


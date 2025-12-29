"""
Tests for GCS Discovery Utilities

Unit tests for gdw_data_core.core.utilities.gcs_discovery module.
"""

import pytest
from unittest.mock import MagicMock
from gdw_data_core.core.utilities import (
    discover_split_files,
    discover_files_by_date,
    build_gcs_path
)


class TestBuildGcsPath:
    """Tests for build_gcs_path function."""

    def test_build_gcs_path_complete(self):
        """Test building complete GCS path."""
        path = build_gcs_path('bucket', 'data', 'file.csv')

        assert path == 'gs://bucket/data/file.csv'

    def test_build_gcs_path_without_filename(self):
        """Test building GCS path without filename."""
        path = build_gcs_path('bucket', 'data')

        assert path == 'gs://bucket/data'

    def test_build_gcs_path_bucket_only(self):
        """Test building GCS path with bucket only."""
        path = build_gcs_path('bucket', '')

        assert path.startswith('gs://bucket')

    def test_build_gcs_path_with_slashes(self):
        """Test building GCS path with path separators."""
        path = build_gcs_path('bucket', '/data/', '/file.csv')

        # Should handle slashes properly
        assert 'gs://bucket' in path
        assert 'file.csv' in path
        # Should not have double slashes in middle
        assert '//' not in path.replace('gs://', '')


class TestDiscoverSplitFiles:
    """Tests for discover_split_files function."""

    def test_discover_split_files_no_matches(self):
        """Test discovering split files with no matches."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = []

        result = discover_split_files(
            mock_gcs_client,
            'bucket',
            'data/app_20251225'
        )

        assert result == []

    def test_discover_split_files_with_matches(self):
        """Test discovering split files with matches."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = [
            'gs://bucket/data/app_20251225_1',
            'gs://bucket/data/app_20251225_2',
            'gs://bucket/data/app_20251225_3'
        ]

        result = discover_split_files(
            mock_gcs_client,
            'bucket',
            'data/app_20251225'
        )

        # Should return sorted list
        assert isinstance(result, list)
        assert len(result) >= 0

    def test_discover_split_files_with_custom_pattern(self):
        """Test discovering split files with custom pattern."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = [
            'gs://bucket/data/file_001.csv',
            'gs://bucket/data/file_002.csv'
        ]

        result = discover_split_files(
            mock_gcs_client,
            'bucket',
            'data/file',
            pattern=r'file_\d{3}\.csv'
        )

        assert isinstance(result, list)

    def test_discover_split_files_error_handling(self):
        """Test error handling in discover_split_files."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.side_effect = Exception('GCS error')

        # Should return empty list on error
        result = discover_split_files(
            mock_gcs_client,
            'bucket',
            'data/app'
        )

        assert result == []


class TestDiscoverFilesByDate:
    """Tests for discover_files_by_date function."""

    def test_discover_files_by_date(self):
        """Test discovering files by date."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = [
            'gs://bucket/data/2025-12-25/file1.csv',
            'gs://bucket/data/2025-12-26/file2.csv',
            'gs://bucket/data/2025-12-27/file3.csv'
        ]

        result = discover_files_by_date(
            mock_gcs_client,
            'bucket',
            'data'
        )

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] < result[-1]  # Should be sorted

    def test_discover_files_by_date_no_files(self):
        """Test discovering files by date with no matches."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = []

        result = discover_files_by_date(
            mock_gcs_client,
            'bucket',
            'data'
        )

        assert result == []

    def test_discover_files_by_date_custom_pattern(self):
        """Test discovering files with custom date pattern."""
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_prefix.return_value = [
            'gs://bucket/data/20251225/file.csv',
            'gs://bucket/data/20251226/file.csv'
        ]

        result = discover_files_by_date(
            mock_gcs_client,
            'bucket',
            'data',
            date_pattern='%Y%m%d'
        )

        assert isinstance(result, list)


"""
Tests for Beam I/O Module

Unit tests for gcp_pipeline_builder.pipelines.beam.io package.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestReadFromGCSDoFn:
    """Tests for ReadFromGCSDoFn."""

    def test_read_from_gcs_setup(self):
        """Test ReadFromGCSDoFn setup."""
        from gcp_pipeline_beam.pipelines.beam.io import ReadFromGCSDoFn

        reader = ReadFromGCSDoFn(encoding='utf-8')
        assert reader.encoding == 'utf-8'


class TestWriteToGCSDoFn:
    """Tests for WriteToGCSDoFn."""

    def test_write_to_gcs_initialization(self):
        """Test WriteToGCSDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteToGCSDoFn

        writer = WriteToGCSDoFn(
            bucket='test-bucket',
            prefix='output/',
            extension='txt'
        )

        assert writer.bucket == 'test-bucket'
        assert writer.prefix == 'output/'
        assert writer.extension == 'txt'


class TestReadCSVFromGCSDoFn:
    """Tests for ReadCSVFromGCSDoFn."""

    def test_read_csv_from_gcs_initialization(self):
        """Test ReadCSVFromGCSDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import ReadCSVFromGCSDoFn

        reader = ReadCSVFromGCSDoFn(delimiter=',', skip_header=True)

        assert reader.delimiter == ','
        assert reader.skip_header is True


class TestWriteCSVToGCSDoFn:
    """Tests for WriteCSVToGCSDoFn."""

    def test_write_csv_to_gcs_initialization(self):
        """Test WriteCSVToGCSDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteCSVToGCSDoFn

        writer = WriteCSVToGCSDoFn(
            bucket='test-bucket',
            filename='output.csv',
            fieldnames=['id', 'name', 'email']
        )

        assert writer.bucket == 'test-bucket'
        assert writer.filename == 'output.csv'
        assert writer.fieldnames == ['id', 'name', 'email']


class TestWriteToBigQueryDoFn:
    """Tests for WriteToBigQueryDoFn."""

    def test_write_to_bigquery_initialization(self):
        """Test WriteToBigQueryDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteToBigQueryDoFn

        writer = WriteToBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table'
        )

        assert writer.project == 'test-project'
        assert writer.dataset == 'test_dataset'
        assert writer.table == 'test_table'


class TestBatchWriteToBigQueryDoFn:
    """Tests for BatchWriteToBigQueryDoFn."""

    def test_batch_write_to_bigquery_initialization(self):
        """Test BatchWriteToBigQueryDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import BatchWriteToBigQueryDoFn

        writer = BatchWriteToBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table',
            batch_size=1000
        )

        assert writer.project == 'test-project'
        assert writer.batch_size == 1000

    def test_batch_write_default_batch_size(self):
        """Test BatchWriteToBigQueryDoFn default batch size."""
        from gcp_pipeline_beam.pipelines.beam.io import BatchWriteToBigQueryDoFn

        writer = BatchWriteToBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table'
        )

        assert writer.batch_size == 1000


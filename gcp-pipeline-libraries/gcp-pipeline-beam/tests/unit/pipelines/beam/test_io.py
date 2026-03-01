"""
Tests for Beam I/O Module

Unit tests for gcp_pipeline_beam.pipelines.beam.io package.
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


class TestReadFromBigQueryDoFn:
    """Tests for ReadFromBigQueryDoFn."""

    def test_read_from_bigquery_initialization(self):
        """Test ReadFromBigQueryDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import ReadFromBigQueryDoFn

        reader = ReadFromBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table'
        )

        assert reader.project == 'test-project'
        assert reader.dataset == 'test_dataset'
        assert reader.table == 'test_table'
        assert reader.query is None

    def test_read_from_bigquery_query_initialization(self):
        """Test ReadFromBigQueryDoFn with query initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import ReadFromBigQueryDoFn

        reader = ReadFromBigQueryDoFn(
            project='test-project',
            query='SELECT * FROM test_dataset.test_table'
        )

        assert reader.project == 'test-project'
        assert reader.query == 'SELECT * FROM test_dataset.test_table'

    def test_read_from_bigquery_process_with_override(self):
        """Test ReadFromBigQueryDoFn process with override element."""
        from gcp_pipeline_beam.pipelines.beam.io import ReadFromBigQueryDoFn
        
        reader = ReadFromBigQueryDoFn(project='test-project')
        
        # We can't easily test the actual BQ call without heavy mocking, 
        # but we can verify the process method accepts an element
        assert hasattr(reader, 'process')
        
        # Test logic for override in process
        element = {'dataset': 'ovr_dataset', 'table': 'ovr_table'}
        
        with patch('google.cloud.bigquery.Client') as mock_client:
            mock_results = [MagicMock(id=1), MagicMock(id=2)]
            mock_client.return_value.list_rows.return_value = mock_results
            
            # Use list() to trigger the generator
            results = list(reader.process(element))
            
            mock_client.return_value.list_rows.assert_called_once_with('test-project.ovr_dataset.ovr_table')


class TestWriteSegmentedToGCSDoFn:
    """Tests for WriteSegmentedToGCSDoFn."""

    def test_write_segmented_to_gcs_initialization(self):
        """Test WriteSegmentedToGCSDoFn initialization."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteSegmentedToGCSDoFn

        writer = WriteSegmentedToGCSDoFn(
            bucket='test-bucket',
            prefix='segments/',
            segment_size=500,
            extension='jsonl'
        )

        assert writer.bucket == 'test-bucket'
        assert writer.prefix == 'segments/'
        assert writer.segment_size == 500
        assert writer.extension == 'jsonl'

    def test_write_segmented_to_gcs_process_buffer(self):
        """Test WriteSegmentedToGCSDoFn buffering."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteSegmentedToGCSDoFn

        writer = WriteSegmentedToGCSDoFn(bucket='test', segment_size=2)
        writer.setup()
        
        # Add one record - should just buffer
        results = list(writer.process({'id': 1}))
        assert len(results) == 0
        assert len(writer.buffer) == 1
        
        # Add second record - should flush (mocked)
        with patch.object(writer, '_flush_segment') as mock_flush:
            mock_flush.return_value = iter(['gs://test/segment_1.json'])
            results = list(writer.process({'id': 2}))
            assert len(results) == 1
            assert results[0] == 'gs://test/segment_1.json'
            mock_flush.assert_called_once()

    def test_write_segmented_to_gcs_flush_error(self):
        """Test WriteSegmentedToGCSDoFn error handling."""
        from gcp_pipeline_beam.pipelines.beam.io import WriteSegmentedToGCSDoFn
        import apache_beam as beam

        writer = WriteSegmentedToGCSDoFn(bucket='test', segment_size=1)
        writer.setup()
        writer.buffer = [{'id': 1}]
        
        # Mock GcsIO to raise error
        writer.gcs_client = MagicMock()
        writer.gcs_client.open.side_effect = Exception("Upload failed")
        
        results = list(writer._flush_segment())
        
        # Should yield TaggedOutput
        assert len(results) == 1
        # Use simple check instead of isinstance if Beam internal types cause issues
        res = results[0]
        assert hasattr(res, 'tag') and res.tag == 'errors'
        assert res.value['error'] == "Upload failed"
        assert res.value['record'] == {'id': 1}
        assert len(writer.buffer) == 0


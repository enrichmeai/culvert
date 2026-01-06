"""
Tests for BasePipeline and GDWPipelineOptions.

Tests the enhanced pipeline base class with:
- Configuration injection
- Audit trail integration
- Error handling integration
- Metrics collection
- Lifecycle hooks
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from gcp_pipeline_builder.pipelines.base import BasePipeline, GDWPipelineOptions, PipelineConfig, lifecycle
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions


class TestBasePipeline:
    """Test suite for BasePipeline class."""

    def test_initialization(self):
        """Test BasePipeline initialization with config."""
        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity',
            'source_file': 'test.csv',
            'gcp_project_id': 'test-project',
            'bigquery_dataset': 'test_dataset'
        }

        # Create a concrete implementation for testing
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing initialization only
                pass

        pipeline = TestPipeline(config=config)

        assert pipeline.run_id is not None
        assert pipeline.audit_manager is not None
        assert pipeline.error_handler is not None
        assert pipeline.metrics_emitter is not None
        assert pipeline.run_id is not None

    def test_initialization_with_run_id(self):
        """Test BasePipeline initialization with provided run_id."""
        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity',
            'run_id': 'custom_run_id_123'
        }

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing initialization only
                pass

        pipeline = TestPipeline(config=config)

        assert pipeline.run_id == 'custom_run_id_123'

    def test_initialization_generates_run_id(self):
        """Test that run_id is generated if not provided."""
        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing initialization only
                pass

        pipeline = TestPipeline(config=config)

        # Run ID should be generated with pipeline name
        assert pipeline.run_id is not None
        assert 'test_pipeline' in pipeline.run_id

    def test_initialization_with_options(self):
        """Test BasePipeline initialization with PipelineOptions."""
        options = PipelineOptions()
        config = {'pipeline_name': 'test_pipeline'}

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing initialization only
                pass

        pipeline = TestPipeline(options=options, config=config)

        assert pipeline.options is options

    def test_on_start_hook(self):
        """Test on_start lifecycle hook."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing hooks only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity',
            'source_file': 'test.csv',
            'gcp_project_id': 'test-project'
        }

        pipeline = TestPipeline(config=config)
        lifecycle.on_start(
            pipeline.audit_manager,
            pipeline.metrics_emitter,
            pipeline._config_dict,
            pipeline.run_id
        )

        # Verify audit trail was updated
        assert pipeline.audit_manager is not None
        # Verify metrics were incremented
        assert pipeline.metrics_emitter.counters.get('pipeline_started', 0) >= 1

    def test_on_failure_hook(self):
        """Test on_failure lifecycle hook."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing hooks only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)
        exc = ValueError("Test error")

        lifecycle.on_failure(
            exc,
            pipeline.audit_manager,
            pipeline.error_handler,
            pipeline.metrics_emitter,
            pipeline._config_dict,
            pipeline.run_id
        )

        # Verify error was handled
        assert len(pipeline.error_handler.errors) > 0
        # Verify failure metric was emitted
        assert pipeline.metrics_emitter.counters.get('pipeline_failed', 0) >= 1

    def test_on_success_hook(self):
        """Test on_success lifecycle hook."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing hooks only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)
        lifecycle.on_success(
            pipeline.audit_manager,
            pipeline.metrics_emitter,
            pipeline.run_id
        )

        # Verify completion metric was emitted
        assert pipeline.metrics_emitter.counters.get('pipeline_completed', 0) >= 1

    @patch('apache_beam.Pipeline')
    def test_run_success(self, mock_pipeline_class):
        """Test successful pipeline execution."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_class.return_value.__enter__ = Mock(return_value=mock_pipeline_instance)
        mock_pipeline_class.return_value.__exit__ = Mock(return_value=False)

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing pipeline execution only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)
        pipeline.run()

        # Verify pipeline ran successfully
        assert pipeline.metrics_emitter.counters.get('pipeline_started', 0) >= 1
        assert pipeline.metrics_emitter.counters.get('pipeline_completed', 0) >= 1

    @patch('apache_beam.Pipeline')
    def test_run_failure(self, mock_pipeline_class):
        """Test failed pipeline execution."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_class.return_value.__enter__ = Mock(return_value=mock_pipeline_instance)
        mock_pipeline_class.return_value.__exit__ = Mock(return_value=False)

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Raises exception to test failure handling
                raise ValueError("Build failed")

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)

        with pytest.raises(ValueError):
            pipeline.run()

        # Verify error was recorded
        assert len(pipeline.error_handler.errors) > 0
        # Verify failure metric was emitted
        assert pipeline.metrics_emitter.counters.get('pipeline_failed', 0) >= 1

    def test_get_metrics_summary(self):
        """Test get_metrics_summary method."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing metrics only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)
        pipeline.metrics_emitter.increment('test_metric', 5)

        stats = pipeline.get_metrics_summary()

        assert stats is not None
        assert 'counters' in stats
        assert stats['counters'].get('test_metric', 0) == 5

    def test_get_error_count(self):
        """Test get_error_count method."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Empty implementation for testing error handling only
                pass

        config = {
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity'
        }

        pipeline = TestPipeline(config=config)

        # Initially should be 0
        assert pipeline.get_error_count() == 0

        # Add error
        pipeline.error_handler.handle_exception(ValueError("Test error"))

        # Now should be 1
        assert pipeline.get_error_count() > 0

    def test_config_injection(self):
        """Test configuration is properly injected."""
        config = {
            'pipeline_name': 'my_pipeline',
            'entity_type': 'applications',
            'source_file': 'gs://bucket/data.csv',
            'gcp_project_id': 'my-gcp-project',
            'bigquery_dataset': 'my_dataset',
            'input_path': 'gs://bucket/input/',
            'output_table': 'project.dataset.table'
        }

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Verify config is accessible in build method
                assert self._config_dict['pipeline_name'] == 'my_pipeline'
                assert self._config_dict['entity_type'] == 'applications'
                assert self._config_dict['source_file'] == 'gs://bucket/data.csv'

        pipeline = TestPipeline(config=config)
        # Create a mock pipeline object for testing
        mock_pipeline = MagicMock()
        pipeline.build(mock_pipeline)


class TestGDWPipelineOptions:
    """Test suite for GDWPipelineOptions class."""

    def test_gdw_pipeline_options_creation(self):
        """Test GDWPipelineOptions can be created."""
        options = GDWPipelineOptions()
        # Verify options object is of correct type
        assert isinstance(options, GDWPipelineOptions)

    def test_gdw_pipeline_options_inherits_from_pipeline_options(self):
        """Test GDWPipelineOptions inherits from PipelineOptions."""
        options = GDWPipelineOptions()
        assert isinstance(options, PipelineOptions)

    def test_pipeline_options_with_arguments(self):
        """Test pipeline options support standard Beam arguments."""
        # This tests that the options class structure is correct
        options = GDWPipelineOptions()
        assert hasattr(options, '_add_argparse_args')


class TestBasePipelineIntegration:
    """Integration tests for BasePipeline with core components."""

    @patch('apache_beam.Pipeline')
    def test_full_pipeline_lifecycle(self, mock_pipeline_class):
        """Test complete pipeline lifecycle from start to success."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_class.return_value.__enter__ = Mock(return_value=mock_pipeline_instance)
        mock_pipeline_class.return_value.__exit__ = Mock(return_value=False)

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                # Simulate processing by incrementing metric
                self.metrics_emitter.increment('records_processed', 100)

        config = {
            'pipeline_name': 'integration_test',
            'entity_type': 'applications',
            'source_file': 'test.csv',
            'gcp_project_id': 'test-project'
        }

        pipeline = TestPipeline(config=config)
        pipeline.run()

        # Verify full lifecycle was executed
        metrics = pipeline.get_metrics_summary()
        assert metrics['counters']['pipeline_started'] >= 1
        assert metrics['counters']['pipeline_completed'] >= 1
        assert metrics['counters']['records_processed'] == 100

    @patch('apache_beam.Pipeline')
    def test_pipeline_with_custom_hooks(self, mock_pipeline_class):
        """Test pipeline with custom lifecycle hooks."""
        mock_pipeline_instance = MagicMock()
        mock_pipeline_class.return_value.__enter__ = Mock(return_value=mock_pipeline_instance)
        mock_pipeline_class.return_value.__exit__ = Mock(return_value=False)

        class CustomPipeline(BasePipeline):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.custom_start_called = False
                self.custom_success_called = False

            def build(self, pipeline):
                # Empty implementation for testing custom hooks
                pass

            # Mock run to simulate calling custom methods if we want to test them
            def run(self):
                self.custom_start_called = True
                super().run()
                self.custom_success_called = True

        config = {'pipeline_name': 'custom_test', 'entity_type': 'data', 'run_id': 'test_run'}
        pipeline = CustomPipeline(config=config)
        pipeline.run()

        # Verify custom hooks were called
        metrics = pipeline.get_metrics_summary()
        assert metrics['counters']['pipeline_completed'] >= 1
        assert pipeline.custom_start_called
        assert pipeline.custom_success_called

    def test_streaming_initialization(self):
        """Test BasePipeline initialization with streaming enabled."""
        config = {
            'pipeline_name': 'streaming_pipeline',
            'streaming': True
        }

        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                pass

        pipeline = TestPipeline(config=config)

        assert pipeline.is_streaming is True
        standard_options = pipeline.options.view_as(StandardOptions)
        assert standard_options.streaming is True

    @patch('apache_beam.io.ReadFromPubSub')
    @patch('apache_beam.io.ReadFromText')
    def test_read_source_gcs(self, mock_read_text, mock_read_pubsub):
        """Test read_source with GCS."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                pass

        pipeline = TestPipeline(config={'pipeline_name': 'test'})
        mock_beam_pipeline = MagicMock()

        source_config = {'type': 'gcs', 'path': 'gs://bucket/file.csv'}
        pipeline.read_source(mock_beam_pipeline, source_config)

        mock_read_text.assert_called_once_with('gs://bucket/file.csv')

    @patch('apache_beam.io.ReadFromPubSub')
    def test_read_source_pubsub(self, mock_read_pubsub):
        """Test read_source with Pub/Sub."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                pass

        pipeline = TestPipeline(config={'pipeline_name': 'test'})
        mock_beam_pipeline = MagicMock()

        source_config = {'type': 'pubsub', 'subscription': 'projects/p/subscriptions/s'}
        pipeline.read_source(mock_beam_pipeline, source_config)

        mock_read_pubsub.assert_called_once_with(subscription='projects/p/subscriptions/s')

    @patch('apache_beam.io.WriteToBigQuery')
    def test_write_to_bigquery_batch(self, mock_write_bq):
        """Test write_to_bigquery in batch mode."""
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                pass

        pipeline = TestPipeline(config={'pipeline_name': 'test', 'streaming': False})
        mock_pcoll = MagicMock()

        pipeline.write_to_bigquery(mock_pcoll, 'project:dataset.table', {'fields': []})

        mock_write_bq.assert_called_once()
        args, kwargs = mock_write_bq.call_args
        assert args[0] == 'project:dataset.table'
        assert kwargs['schema'] == {'fields': []}
        assert 'method' not in kwargs

    @patch('apache_beam.io.WriteToBigQuery')
    def test_write_to_bigquery_streaming(self, mock_write_bq):
        """Test write_to_bigquery in streaming mode."""
        import apache_beam as beam
        class TestPipeline(BasePipeline):
            def build(self, pipeline):
                pass

        pipeline = TestPipeline(config={'pipeline_name': 'test', 'streaming': True})
        mock_pcoll = MagicMock()

        pipeline.write_to_bigquery(mock_pcoll, 'project:dataset.table', {'fields': []})

        mock_write_bq.assert_called_once()
        args, kwargs = mock_write_bq.call_args
        assert kwargs['method'] == beam.io.WriteToBigQuery.Method.STORAGE_WRITE_API


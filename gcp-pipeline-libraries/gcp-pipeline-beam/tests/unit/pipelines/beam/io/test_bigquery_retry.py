"""
Unit tests for BigQuery retry logic module.

Tests cover:
- Transient quota errors
- Rate limit handling
- Table lock errors
- Load job timeouts
- Exponential backoff calculation
- Dead letter queue routing
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta
import time

from gcp_pipeline_beam.pipelines.beam.io.bigquery_retry import (
    BigQueryRetryConfig,
    BigQueryErrorType,
    BigQueryErrorClassifier,
    ResilientWriteToBigQueryDoFn,
    BatchResilientWriteToBigQueryDoFn,
    RetryState,
)


class TestBigQueryRetryConfig:
    """Tests for BigQueryRetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BigQueryRetryConfig()

        assert config.max_retries == 5
        assert config.initial_delay_seconds == 1.0
        assert config.max_delay_seconds == 300.0
        assert config.backoff_multiplier == 2.0
        assert config.quota_retry_delay == 60.0
        assert config.table_lock_retry_delay == 30.0
        assert config.batch_size == 500

    def test_custom_config(self):
        """Test custom configuration."""
        config = BigQueryRetryConfig(
            max_retries=10,
            quota_retry_delay=120.0,
            batch_size=1000
        )

        assert config.max_retries == 10
        assert config.quota_retry_delay == 120.0
        assert config.batch_size == 1000


class TestBigQueryErrorClassifier:
    """Tests for BigQueryErrorClassifier."""

    def test_classify_quota_exceeded(self):
        """Test classification of quota exceeded errors."""
        error = Exception("Quota exceeded for project my-project")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.QUOTA_EXCEEDED
        assert is_retryable is True

    def test_classify_rate_limit(self):
        """Test classification of rate limit errors."""
        error = Exception("Rate limit exceeded. Please slow down.")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.RATE_LIMIT
        assert is_retryable is True

    def test_classify_table_lock(self):
        """Test classification of table lock errors."""
        error = Exception("Table is locked by another operation")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.TABLE_LOCK
        assert is_retryable is True

    def test_classify_backend_error(self):
        """Test classification of backend errors."""
        error = Exception("Backend error: Service unavailable")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.BACKEND_ERROR
        assert is_retryable is True

    def test_classify_timeout(self):
        """Test classification of timeout errors."""
        error = Exception("Operation timed out after 600 seconds")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.TIMEOUT
        assert is_retryable is True

    def test_classify_invalid_data(self):
        """Test classification of invalid data errors."""
        error = Exception("Invalid value for field 'date': could not convert")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.INVALID_DATA
        assert is_retryable is False

    def test_classify_schema_mismatch(self):
        """Test classification of schema mismatch errors."""
        error = Exception("Schema mismatch: expected INTEGER but got STRING")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.SCHEMA_MISMATCH
        assert is_retryable is False

    def test_classify_not_found(self):
        """Test classification of not found errors."""
        error = Exception("Table my-project.dataset.table not found")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.NOT_FOUND
        assert is_retryable is False

    def test_classify_permission_denied(self):
        """Test classification of permission denied errors."""
        error = Exception("Permission denied: User does not have access")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.PERMISSION_DENIED
        assert is_retryable is False

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        error = Exception("Something completely unexpected happened")
        error_type, is_retryable = BigQueryErrorClassifier.classify(error)

        assert error_type == BigQueryErrorType.UNKNOWN
        assert is_retryable is False

    def test_get_retry_delay_quota_error(self):
        """Test retry delay calculation for quota errors."""
        config = BigQueryRetryConfig(quota_retry_delay=60.0)

        delay = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.QUOTA_EXCEEDED,
            config,
            retry_count=0
        )

        # Should be at least quota_retry_delay
        assert delay >= 60.0

    def test_get_retry_delay_table_lock(self):
        """Test retry delay calculation for table lock errors."""
        config = BigQueryRetryConfig(table_lock_retry_delay=30.0)

        delay = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.TABLE_LOCK,
            config,
            retry_count=0
        )

        # Should be at least table_lock_retry_delay
        assert delay >= 30.0

    def test_get_retry_delay_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = BigQueryRetryConfig(
            initial_delay_seconds=1.0,
            backoff_multiplier=2.0,
            jitter_fraction=0.0  # Disable jitter for predictable test
        )

        delay_0 = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.BACKEND_ERROR,
            config,
            retry_count=0
        )
        delay_1 = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.BACKEND_ERROR,
            config,
            retry_count=1
        )
        delay_2 = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.BACKEND_ERROR,
            config,
            retry_count=2
        )

        # With no jitter, delays should follow exponential pattern
        assert delay_1 > delay_0
        assert delay_2 > delay_1

    def test_get_retry_delay_max_cap(self):
        """Test that delay is capped at max_delay_seconds."""
        config = BigQueryRetryConfig(
            initial_delay_seconds=10.0,
            backoff_multiplier=10.0,
            max_delay_seconds=60.0,
            jitter_fraction=0.0
        )

        delay = BigQueryErrorClassifier.get_retry_delay(
            BigQueryErrorType.BACKEND_ERROR,
            config,
            retry_count=10  # Would be very large without cap
        )

        # With jitter disabled, should be exactly max
        assert delay == 60.0


class TestRetryState:
    """Tests for RetryState dataclass."""

    def test_initial_state(self):
        """Test initial state values."""
        state = RetryState(record_id="test-123")

        assert state.record_id == "test-123"
        assert state.retry_count == 0
        assert state.last_error is None
        assert state.total_delay_seconds == 0.0

    def test_state_mutation(self):
        """Test state can be mutated."""
        state = RetryState(record_id="test-123")

        state.retry_count = 3
        state.last_error = "Quota exceeded"
        state.total_delay_seconds = 90.0

        assert state.retry_count == 3
        assert state.last_error == "Quota exceeded"
        assert state.total_delay_seconds == 90.0


class TestResilientWriteToBigQueryDoFn:
    """Tests for ResilientWriteToBigQueryDoFn."""

    @pytest.fixture
    def writer(self):
        """Create a writer instance."""
        return ResilientWriteToBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table',
            config=BigQueryRetryConfig(max_retries=3),
            run_id='test-run-123'
        )

    @patch('gcp_pipeline_beam.pipelines.beam.io.bigquery_retry.time.sleep')
    def test_successful_write(self, mock_sleep, writer):
        """Test successful write without errors."""
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []  # No errors
        writer.client = mock_client
        writer.table_ref = 'test-project.test_dataset.test_table'

        record = {'id': '1', 'name': 'Test'}
        results = list(writer.process(record))

        assert len(results) == 1
        assert results[0] == record
        mock_sleep.assert_not_called()

    @patch('gcp_pipeline_beam.pipelines.beam.io.bigquery_retry.time.sleep')
    def test_retry_on_quota_error(self, mock_sleep, writer):
        """Test retry behavior on quota error."""
        mock_client = MagicMock()
        # First call fails with quota error, second succeeds
        mock_client.insert_rows_json.side_effect = [
            [{'errors': [{'message': 'Quota exceeded'}]}],
            []  # Success
        ]
        writer.client = mock_client
        writer.table_ref = 'test-project.test_dataset.test_table'

        record = {'id': '1', 'name': 'Test'}
        results = list(writer.process(record))

        assert len(results) == 1
        assert results[0] == record
        mock_sleep.assert_called_once()

    @patch('gcp_pipeline_beam.pipelines.beam.io.bigquery_retry.time.sleep')
    def test_dead_letter_after_max_retries(self, mock_sleep, writer):
        """Test routing to dead letter after exhausting retries."""
        mock_client = MagicMock()
        # Always fail with retryable error
        mock_client.insert_rows_json.return_value = [
            {'errors': [{'message': 'Quota exceeded'}]}
        ]
        writer.client = mock_client
        writer.table_ref = 'test-project.test_dataset.test_table'
        writer.config = BigQueryRetryConfig(max_retries=2)

        record = {'id': '1', 'name': 'Test'}
        results = list(writer.process(record))

        # Should route to dead_letter
        import apache_beam as beam
        tagged_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(tagged_outputs) == 1
        assert tagged_outputs[0].tag == 'dead_letter'
        assert tagged_outputs[0].value['retry_count'] == 2

    @patch('gcp_pipeline_beam.pipelines.beam.io.bigquery_retry.time.sleep')
    def test_non_retryable_error_to_errors(self, mock_sleep, writer):
        """Test non-retryable errors route to errors output."""
        mock_client = MagicMock()
        # Non-retryable error
        mock_client.insert_rows_json.return_value = [
            {'errors': [{'message': 'Invalid value for field date'}]}
        ]
        writer.client = mock_client
        writer.table_ref = 'test-project.test_dataset.test_table'

        record = {'id': '1', 'date': 'not-a-date'}
        results = list(writer.process(record))

        import apache_beam as beam
        tagged_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(tagged_outputs) == 1
        assert tagged_outputs[0].tag == 'errors'
        mock_sleep.assert_not_called()  # No retry for non-retryable errors


class TestBatchResilientWriteToBigQueryDoFn:
    """Tests for BatchResilientWriteToBigQueryDoFn."""

    @pytest.fixture
    def batch_writer(self):
        """Create a batch writer instance."""
        return BatchResilientWriteToBigQueryDoFn(
            project='test-project',
            dataset='test_dataset',
            table='test_table',
            batch_size=2,
            config=BigQueryRetryConfig(max_retries=3),
            run_id='test-run-123'
        )

    def test_batch_buffering(self, batch_writer):
        """Test that records are buffered."""
        batch_writer.batch = []

        # Process one record (below batch size)
        list(batch_writer.process({'id': '1'}))

        assert len(batch_writer.batch) == 1

    @patch('gcp_pipeline_beam.pipelines.beam.io.bigquery_retry.time.sleep')
    def test_batch_flush_on_full(self, mock_sleep, batch_writer):
        """Test batch flushes when full."""
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []  # Success
        batch_writer.client = mock_client
        batch_writer.table_ref = 'test-project.test_dataset.test_table'
        batch_writer.batch = []

        # Process records up to batch size
        list(batch_writer.process({'id': '1'}))
        list(batch_writer.process({'id': '2'}))  # Should trigger flush

        # insert_rows_json should have been called
        mock_client.insert_rows_json.assert_called_once()


class TestBigQueryErrorType:
    """Tests for BigQueryErrorType enum."""

    def test_error_types_exist(self):
        """Test that all expected error types exist."""
        assert BigQueryErrorType.QUOTA_EXCEEDED
        assert BigQueryErrorType.RATE_LIMIT
        assert BigQueryErrorType.TABLE_LOCK
        assert BigQueryErrorType.BACKEND_ERROR
        assert BigQueryErrorType.TIMEOUT
        assert BigQueryErrorType.INVALID_DATA
        assert BigQueryErrorType.SCHEMA_MISMATCH
        assert BigQueryErrorType.NOT_FOUND
        assert BigQueryErrorType.PERMISSION_DENIED
        assert BigQueryErrorType.RESOURCE_EXHAUSTED
        assert BigQueryErrorType.UNKNOWN

    def test_error_type_values(self):
        """Test error type values are strings."""
        assert BigQueryErrorType.QUOTA_EXCEEDED.value == "QUOTA_EXCEEDED"
        assert BigQueryErrorType.TABLE_LOCK.value == "TABLE_LOCK"


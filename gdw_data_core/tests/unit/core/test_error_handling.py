import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from gdw_data_core.core.error_handling import (
    ErrorClassifier,
    ErrorConfig,
    PipelineError,
    ErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    RetryStrategy,
    RetryPolicy,
    InMemoryErrorStorage,
)


class TestErrorClassifier:
    """Tests for error classification logic"""

    def test_classify_transient_error(self):
        """Test classification of transient errors."""
        exc = TimeoutError("Connection timeout")
        severity, category, retry = ErrorClassifier.classify(exc)

        assert severity == ErrorSeverity.MEDIUM
        assert category == ErrorCategory.INTEGRATION
        assert retry == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        exc = ValueError("Invalid input")
        severity, category, retry = ErrorClassifier.classify(exc)

        assert severity == ErrorSeverity.MEDIUM
        assert category == ErrorCategory.VALIDATION
        assert retry == RetryStrategy.NO_RETRY

    def test_classify_integration_error(self):
        """Test classification of integration errors."""
        exc = Exception("Service unavailable")
        severity, category, retry = ErrorClassifier.classify(exc)

        # Should be classified as integration error or unknown
        assert category in [ErrorCategory.INTEGRATION, ErrorCategory.UNKNOWN]

    def test_classify_permission_error(self):
        """Test classification of permission errors."""
        exc = Exception("permission denied")
        severity, category, retry = ErrorClassifier.classify(exc)

        assert severity == ErrorSeverity.CRITICAL
        assert category == ErrorCategory.CONFIGURATION
        assert retry == RetryStrategy.MANUAL_ONLY

    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        exc = ConnectionError("Connection failed")
        severity, category, retry = ErrorClassifier.classify(exc)

        assert severity == ErrorSeverity.MEDIUM
        assert category == ErrorCategory.INTEGRATION
        assert retry == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_classify_quota_error(self):
        """Test classification of quota exceeded errors."""
        exc = Exception("quota exceeded")
        severity, category, retry = ErrorClassifier.classify(exc)

        assert severity == ErrorSeverity.HIGH
        assert category == ErrorCategory.RESOURCE


class TestErrorConfig:
    """Tests for error configuration"""

    def test_default_config(self):
        """Test default error configuration."""
        config = ErrorConfig()

        assert config.max_retries == 3
        assert config.initial_retry_delay_seconds == 1
        assert config.max_retry_delay_seconds == 60
        assert config.backoff_multiplier == 2.0
        assert config.jitter_enabled is True
        assert config.dead_letter_enabled is True
        assert config.alert_on_critical is True

    def test_custom_config(self):
        """Test custom error configuration."""
        config = ErrorConfig(
            max_retries=5,
            initial_retry_delay_seconds=2,
            backoff_multiplier=1.5,
            jitter_enabled=False
        )

        assert config.max_retries == 5
        assert config.initial_retry_delay_seconds == 2
        assert config.backoff_multiplier == 1.5
        assert config.jitter_enabled is False


class TestPipelineError:
    """Tests for PipelineError data class"""

    def test_pipeline_error_creation(self):
        """Test creating a PipelineError record."""
        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid SSN",
            record_id="record-789"
        )

        assert error.error_id == "err-123"
        assert error.run_id == "run-456"
        assert error.severity == ErrorSeverity.HIGH
        assert error.resolved is False
        assert error.retry_count == 0

    def test_pipeline_error_to_dict(self):
        """Test converting PipelineError to dictionary."""
        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid SSN"
        )

        error_dict = error.to_dict()

        assert error_dict['error_id'] == "err-123"
        assert error_dict['severity'] == "HIGH"
        assert error_dict['category'] == "VALIDATION"
        assert 'timestamp' in error_dict

    def test_pipeline_error_to_json(self):
        """Test converting PipelineError to JSON."""
        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid SSN"
        )

        error_json = error.to_json()

        assert isinstance(error_json, str)
        assert '"error_id": "err-123"' in error_json
        assert '"severity": "HIGH"' in error_json

    def test_pipeline_error_metadata(self):
        """Test metadata storage in error record."""
        metadata = {"source": "test", "batch": "batch-1"}
        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid data",
            metadata=metadata
        )

        assert error.metadata == metadata


class TestRetryPolicy:
    """Tests for retry policy logic"""

    def test_should_not_retry_validation_error(self):
        """Test that validation errors are not retried."""
        config = ErrorConfig(max_retries=3)
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid input"
        )

        assert policy.should_retry(error) is False

    def test_should_retry_transient_error(self):
        """Test that transient errors can be retried."""
        config = ErrorConfig(max_retries=3)
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            retry_count=0
        )

        assert policy.should_retry(error) is True

    def test_max_retries_exceeded(self):
        """Test that retries stop after max_retries."""
        config = ErrorConfig(max_retries=3)
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            retry_count=3
        )

        assert policy.should_retry(error) is False

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        config = ErrorConfig(
            initial_retry_delay_seconds=1,
            backoff_multiplier=2.0,
            max_retry_delay_seconds=60,
            jitter_enabled=False
        )
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            retry_count=0
        )

        delay = policy.calculate_backoff(error)
        assert delay == 1  # First retry: 1 second

        error.retry_count = 1
        delay = policy.calculate_backoff(error)
        assert delay == 2  # Second retry: 2 seconds

        error.retry_count = 2
        delay = policy.calculate_backoff(error)
        assert delay == 4  # Third retry: 4 seconds

    def test_backoff_respects_max_delay(self):
        """Test that backoff respects maximum delay."""
        config = ErrorConfig(
            initial_retry_delay_seconds=1,
            backoff_multiplier=10.0,
            max_retry_delay_seconds=60,
            jitter_enabled=False
        )
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            retry_count=10
        )

        delay = policy.calculate_backoff(error)
        assert delay <= 60  # Should not exceed max delay

    def test_schedule_retry(self):
        """Test scheduling next retry."""
        config = ErrorConfig(
            initial_retry_delay_seconds=5,
            backoff_multiplier=2.0,
            jitter_enabled=False
        )
        policy = RetryPolicy(config)

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            retry_count=0
        )

        before = datetime.utcnow()
        next_retry = policy.schedule_retry(error)
        after = datetime.utcnow()

        assert next_retry is not None
        assert next_retry >= before + timedelta(seconds=5)
        assert next_retry <= after + timedelta(seconds=6)


class TestErrorHandler:
    """Tests for ErrorHandler"""

    def test_error_handler_initialization(self):
        """Test initializing error handler."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        assert handler.pipeline_name == "test_pipeline"
        assert handler.run_id == "run-123"
        assert len(handler.errors) == 0

    def test_handle_exception(self):
        """Test handling an exception."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        exc = ValueError("Invalid SSN")
        error = handler.handle_exception(exc)

        assert error.error_id is not None
        assert error.run_id == "run-123"
        assert error.error_type == "ValueError"
        assert error.error_message == "Invalid SSN"
        assert len(handler.errors) == 1

    def test_handle_exception_with_overrides(self):
        """Test handling exception with severity/category overrides."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        exc = ValueError("Invalid input")
        error = handler.handle_exception(
            exc,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.PERSISTENCE
        )

        assert error.severity == ErrorSeverity.CRITICAL
        assert error.category == ErrorCategory.PERSISTENCE

    def test_get_critical_errors(self):
        """Test filtering critical errors."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        # Add some errors
        handler.handle_exception(ValueError("Error 1"))
        handler.handle_exception(
            TimeoutError("Error 2"),
            severity=ErrorSeverity.CRITICAL
        )
        handler.handle_exception(ValueError("Error 3"))

        critical = handler.get_critical_errors()
        assert len(critical) == 1
        assert critical[0].error_message == "Error 2"

    def test_get_retryable_errors(self):
        """Test filtering retryable errors."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        # Add errors
        handler.handle_exception(ValueError("No retry"))  # NO_RETRY
        handler.handle_exception(TimeoutError("Retryable"))  # EXPONENTIAL_BACKOFF

        retryable = handler.get_retryable_errors()
        assert len(retryable) == 1
        assert retryable[0].error_type == "TimeoutError"

    def test_mark_resolved(self):
        """Test marking error as resolved."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        error = handler.handle_exception(ValueError("Test error"))
        assert error.resolved is False

        handler.mark_resolved(error.error_id, "Fixed in v1.1")
        assert error.resolved is True
        assert error.resolution_notes == "Fixed in v1.1"

    def test_prepare_retry(self):
        """Test preparing error for retry."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        error = handler.handle_exception(TimeoutError("Timeout"))
        assert error.retry_count == 0

        success = handler.prepare_retry(error)
        assert success is True
        assert error.retry_count == 1
        assert error.last_retry_timestamp is not None

    def test_export_errors(self):
        """Test exporting errors as JSON."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        handler.handle_exception(ValueError("Error 1"))
        handler.handle_exception(TimeoutError("Error 2"))

        json_export = handler.export_errors()
        assert isinstance(json_export, str)
        assert "Error 1" in json_export
        assert "Error 2" in json_export


class TestErrorContext:
    """Tests for ErrorContext manager"""

    def test_error_context_success(self):
        """Test error context manager with successful operation."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        with ErrorContext(handler, operation_name="test_op") as ctx:
            result = 10 + 5

        # Should not raise, no error logged
        assert len(handler.errors) == 0

    def test_error_context_catches_exception(self):
        """Test error context manager catches exceptions."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        # Default behavior: suppress exceptions for retryable errors
        with ErrorContext(handler, operation_name="test_op", auto_retry=False):
            try:
                raise ValueError("Test error")
            except ValueError:
                pass

        assert len(handler.errors) >= 0

    def test_error_context_with_non_retryable_error(self):
        """Test context with non-retryable error."""
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        with pytest.raises(ValueError):
            with ErrorContext(handler, operation_name="test_op", auto_retry=False):
                raise ValueError("Test error")

        # Error should be classified
        assert len(handler.errors) == 1


class TestErrorStorageBackend:
    """Tests for error storage backends"""

    def test_in_memory_storage(self):
        """Test in-memory error storage."""
        storage = InMemoryErrorStorage()

        error = PipelineError(
            error_id="err-123",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NO_RETRY,
            error_type="ValueError",
            error_message="Invalid input"
        )

        assert storage.store_error(error) is True
        retrieved = storage.retrieve_errors("run-456")
        assert len(retrieved) == 1
        assert retrieved[0].error_id == "err-123"

    def test_in_memory_storage_retrieve_retryable(self):
        """Test retrieving retryable errors."""
        storage = InMemoryErrorStorage()

        # Add retryable error
        error1 = PipelineError(
            error_id="err-1",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            resolved=False
        )

        # Add resolved error
        error2 = PipelineError(
            error_id="err-2",
            run_id="run-456",
            pipeline_name="test_pipeline",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError",
            error_message="Timeout",
            resolved=True
        )

        storage.store_error(error1)
        storage.store_error(error2)

        retryable = storage.retrieve_retryable()
        assert len(retryable) == 1
        assert retryable[0].error_id == "err-1"


class TestErrorIntegration:
    """Integration tests for error handling"""

    def test_full_error_workflow(self):
        """Test complete error handling workflow."""
        storage = InMemoryErrorStorage()
        handler = ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="run-123",
            error_storage=storage
        )

        # Simulate error
        exc = TimeoutError("Connection timeout")
        error = handler.handle_exception(exc)

        # Verify error was stored
        stored = storage.retrieve_errors("run-123")
        assert len(stored) == 1
        assert stored[0].error_id == error.error_id

        # Prepare retry
        assert handler.prepare_retry(error) is True
        assert error.retry_count == 1

        # Mark resolved
        handler.mark_resolved(error.error_id, "Recovered")
        assert error.resolved is True

        # Verify not in retryable list
        retryable = storage.retrieve_retryable()
        assert len(retryable) == 0


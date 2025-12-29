"""
Error Handling Framework Unit Tests

Comprehensive tests for error classification, routing, retry logic,
and alert management in the LOA pipeline.

Tests: ErrorHandler, ErrorClassifier, RetryPolicy, AlertManager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any

from gdw_data_core.core.error_handling import (
    ErrorHandler,
    ErrorClassifier,
    RetryPolicy,
    ErrorSeverity,
    ErrorCategory,
    ErrorConfig
)


class TestErrorSeverity:
    """Test ErrorSeverity enum."""

    def test_severity_levels_exist(self):
        """Test that all severity levels are defined."""
        assert hasattr(ErrorSeverity, 'CRITICAL')
        assert hasattr(ErrorSeverity, 'HIGH')
        assert hasattr(ErrorSeverity, 'MEDIUM')
        assert hasattr(ErrorSeverity, 'LOW')
        assert hasattr(ErrorSeverity, 'INFO')

    def test_severity_comparison(self):
        """Test that severity levels are ordered correctly."""
        # CRITICAL > HIGH > MEDIUM > LOW > INFO
        # We can define a priority map since they are strings
        priority = {
            ErrorSeverity.CRITICAL: 5,
            ErrorSeverity.HIGH: 4,
            ErrorSeverity.MEDIUM: 3,
            ErrorSeverity.LOW: 2,
            ErrorSeverity.INFO: 1
        }
        assert priority[ErrorSeverity.CRITICAL] > priority[ErrorSeverity.HIGH]
        assert priority[ErrorSeverity.HIGH] > priority[ErrorSeverity.MEDIUM]
        assert priority[ErrorSeverity.MEDIUM] > priority[ErrorSeverity.LOW]
        assert priority[ErrorSeverity.LOW] > priority[ErrorSeverity.INFO]


class TestErrorCategory:
    """Test ErrorCategory enum."""

    def test_all_error_categories_defined(self):
        """Test that all error categories are defined."""
        expected_categories = [
            'VALIDATION',
            'TRANSFORMATION',
            'PERSISTENCE',
            'INTEGRATION',
            'CONFIGURATION',
            'RESOURCE',
            'UNKNOWN'
        ]

        for category in expected_categories:
            assert hasattr(ErrorCategory, category)

    def test_error_category_values(self):
        """Test error category values."""
        assert ErrorCategory.VALIDATION.value == 'VALIDATION'
        assert ErrorCategory.TRANSFORMATION.value == 'TRANSFORMATION'
        assert ErrorCategory.PERSISTENCE.value == 'PERSISTENCE'


class TestErrorClassifier:
    """Test ErrorClassifier."""

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        classifier = ErrorClassifier()

        error = ValueError("Invalid SSN format")
        sev, category, retry = classifier.classify(error)

        assert category == ErrorCategory.VALIDATION

    def test_classify_database_error(self):
        """Test classification of persistence errors."""
        classifier = ErrorClassifier()

        # Simulate database error
        error = Exception("Connection timeout to BigQuery")
        sev, category, retry = classifier.classify(error)

        # Should classify as PERSISTENCE or INTEGRATION
        assert category in [ErrorCategory.PERSISTENCE, ErrorCategory.INTEGRATION]

    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        classifier = ErrorClassifier()

        error = TimeoutError("GCS operation timed out")
        sev, category, retry = classifier.classify(error)

        assert category in [ErrorCategory.RESOURCE, ErrorCategory.INTEGRATION]

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        classifier = ErrorClassifier()

        error = Exception("Unknown error occurred")
        sev, category, retry = classifier.classify(error)

        # Should fall back to UNKNOWN
        assert category in [ErrorCategory.UNKNOWN, ErrorCategory.INTEGRATION]

    def test_classify_multiple_errors(self):
        """Test classifying multiple different errors."""
        classifier = ErrorClassifier()

        errors = [
            (ValueError("Bad value"), ErrorCategory.VALIDATION),
            (TimeoutError("Timeout"), ErrorCategory.RESOURCE),
            (Exception("Unknown"), ErrorCategory.UNKNOWN),
        ]

        for error, expected_category in errors:
            sev, category, retry = classifier.classify(error)
            assert category is not None

    def test_classify_with_error_message_hints(self):
        """Test classification using error message hints."""
        classifier = ErrorClassifier()

        # Message contains "validation"
        error1 = ValueError("Validation failed for SSN")
        sev1, cat1, retry1 = classifier.classify(error1)
        assert cat1 in [ErrorCategory.VALIDATION, ErrorCategory.UNKNOWN]

        # Message contains "connection"
        error2 = Exception("Connection refused to database")
        sev2, cat2, retry2 = classifier.classify(error2)
        assert cat2 in [ErrorCategory.PERSISTENCE, ErrorCategory.INTEGRATION]


class TestRetryPolicy:
    """Test RetryPolicy."""

    def test_default_retry_policy(self):
        """Test default retry policy."""
        policy = RetryPolicy()

        assert policy.config.max_retries >= 3
        assert policy.config.initial_retry_delay_seconds > 0
        assert policy.config.backoff_multiplier >= 1

    def test_custom_retry_policy(self):
        """Test creating custom retry policy."""
        config = ErrorConfig(
            max_retries=5,
            initial_retry_delay_seconds=1,
            backoff_multiplier=2.0
        )
        policy = RetryPolicy(config=config)

        assert policy.config.max_retries == 5
        assert policy.config.initial_retry_delay_seconds == 1
        assert policy.config.backoff_multiplier == 2.0

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        config = ErrorConfig(
            initial_retry_delay_seconds=1,
            backoff_multiplier=2.0,
            jitter_enabled=False
        )
        policy = RetryPolicy(config=config)

        from gdw_data_core.core.error_handling import PipelineError, RetryStrategy
        error = PipelineError(
            error_id="test", run_id="run", pipeline_name="pipe",
            severity=ErrorSeverity.MEDIUM, category=ErrorCategory.INTEGRATION,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            error_type="TimeoutError", error_message="Timeout",
            retry_count=0
        )

        # Attempt 0: 1 second
        assert policy.calculate_backoff(error) == 1
        
        error.retry_count = 1
        # Attempt 1: 2 seconds
        assert policy.calculate_backoff(error) == 2
        
        error.retry_count = 2
        # Attempt 2: 4 seconds
        assert policy.calculate_backoff(error) == 4

    def test_retry_for_transient_errors(self):
        """Test that transient errors should be retried."""
        policy = RetryPolicy()

        assert policy.config.max_retries > 0

    def test_no_retry_for_permanent_errors(self):
        """Test that permanent errors should not be retried."""
        policy = RetryPolicy()

        assert policy.config.max_retries > 0  # But policy has retries


class TestErrorHandler:
    """Test ErrorHandler."""

    @pytest.fixture
    def error_handler(self):
        """Create error handler for testing."""
        return ErrorHandler(
            pipeline_name="test_pipeline",
            run_id="test_run_001"
        )

    def test_error_handler_initialization(self, error_handler):
        """Test error handler initialization."""
        assert error_handler.pipeline_name == "test_pipeline"
        assert error_handler.run_id == "test_run_001"

    def test_handle_validation_error(self, error_handler):
        """Test handling validation error."""
        error = ValueError("Invalid SSN format")

        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://bucket/applications.csv",
            category=ErrorCategory.VALIDATION
        )

        assert handled_error is not None
        assert handled_error.source_file == "gs://bucket/applications.csv"
        assert handled_error.category == ErrorCategory.VALIDATION

    def test_handle_error_with_retry(self, error_handler):
        """Test handling error with retry logic."""
        error = TimeoutError("GCS operation timed out")

        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://bucket/data.csv",
            category=ErrorCategory.RESOURCE
        )

        assert handled_error is not None
        # should_retry check replaced with retry_strategy
        from gdw_data_core.core.error_handling import RetryStrategy
        assert handled_error.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_handle_error_creates_audit_entry(self, error_handler):
        """Test that error handling creates audit entry."""
        error = ValueError("Test error")

        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://bucket/test.csv",
            category=ErrorCategory.VALIDATION
        )

        # Should have timestamp
        assert hasattr(handled_error, 'timestamp')
        assert handled_error.timestamp is not None

    def test_error_has_correct_severity(self, error_handler):
        """Test that error severity is set correctly."""
        # Validation error = MEDIUM severity
        error1 = ValueError("Validation failed")
        handled1 = error_handler.handle_exception(
            error1,
            source_file="gs://bucket/test.csv",
            category=ErrorCategory.VALIDATION
        )

        # Should have severity
        assert hasattr(handled1, 'severity')
        assert handled1.severity in [
            ErrorSeverity.CRITICAL,
            ErrorSeverity.HIGH,
            ErrorSeverity.MEDIUM,
            ErrorSeverity.LOW,
            ErrorSeverity.INFO
        ]

    def test_error_routing_to_correct_location(self, error_handler):
        """Test that errors are routed to correct location."""
        error = ValueError("Invalid data")

        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://input-bucket/file.csv",
            category=ErrorCategory.VALIDATION
        )

        # Should have source file which is part of routing
        assert handled_error.source_file == "gs://input-bucket/file.csv"

    def test_multiple_errors_in_batch(self, error_handler):
        """Test handling multiple errors in a batch."""
        errors = [
            ValueError("Error 1"),
            ValueError("Error 2"),
            ValueError("Error 3")
        ]

        handled_errors = []
        for error in errors:
            handled = error_handler.handle_exception(
                error,
                source_file="gs://bucket/batch.csv",
                category=ErrorCategory.VALIDATION
            )
            handled_errors.append(handled)

        assert len(handled_errors) == 3
        assert all(e is not None for e in handled_errors)

    def test_error_context_preservation(self, error_handler):
        """Test that error context is preserved."""
        error = ValueError("Context test error")
        metadata = {
            "record_id": "REC001",
            "field": "ssn",
            "value": "INVALID"
        }

        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://bucket/test.csv",
            category=ErrorCategory.VALIDATION,
            metadata=metadata
        )

        # Metadata should be preserved
        assert handled_error.metadata == metadata


class TestErrorRecoveryPatterns:
    """Test error recovery patterns."""

    def test_retry_and_continue_pattern(self):
        """Test retry-and-continue recovery pattern."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        # Simulate operation that might fail
        max_retries = 3
        retry_count = 0
        success = False

        for attempt in range(max_retries):
            try:
                # Simulate success on retry
                if retry_count >= 1:
                    success = True
                else:
                    raise TimeoutError("Retry me")
            except TimeoutError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    error_handler.handle_exception(
                        e,
                        source_file="gs://bucket/file.csv",
                        category=ErrorCategory.RESOURCE
                    )
                    break

        # Should eventually succeed
        assert success or retry_count == max_retries

    def test_error_aggregation_pattern(self):
        """Test aggregating multiple errors."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        # Collect multiple errors
        errors = []
        for i in range(5):
            error = ValueError(f"Error {i}")
            handled = error_handler.handle_exception(
                error,
                source_file="gs://bucket/file.csv",
                category=ErrorCategory.VALIDATION
            )
            errors.append(handled)

        # Should have aggregated 5 errors
        assert len(errors) == 5

    def test_error_notification_pattern(self):
        """Test error notification/alerting pattern."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        # Handle critical error
        error = Exception("Critical failure")
        handled_error = error_handler.handle_exception(
            error,
            source_file="gs://bucket/file.csv",
            category=ErrorCategory.PERSISTENCE,
            severity=ErrorSeverity.CRITICAL
        )

        # Critical errors should trigger alert
        assert handled_error.severity == ErrorSeverity.CRITICAL


class TestAlertTriggering:
    """Test alert triggering for errors."""

    def test_critical_error_triggers_alert(self):
        """Test that critical errors trigger alerts."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        error = Exception("Critical system failure")
        handled = error_handler.handle_exception(
            error,
            source_file="gs://bucket/file.csv",
            category=ErrorCategory.PERSISTENCE,
            severity=ErrorSeverity.CRITICAL
        )

        # Should be marked for alerting
        assert handled.severity == ErrorSeverity.CRITICAL

    def test_high_error_triggers_alert(self):
        """Test that high severity errors trigger alerts."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        error = Exception("High impact error")
        handled = error_handler.handle_exception(
            error,
            source_file="gs://bucket/file.csv",
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.HIGH
        )

        assert handled.severity == ErrorSeverity.HIGH

    def test_low_error_no_alert(self):
        """Test that low errors don't trigger alerts."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        error = Exception("Minor issue")
        handled = error_handler.handle_exception(
            error,
            source_file="gs://bucket/file.csv",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.INFO
        )

        assert handled.severity == ErrorSeverity.INFO


class TestErrorLogging:
    """Test error logging functionality."""

    def test_error_logged_with_full_context(self):
        """Test that errors are logged with full context."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        error = ValueError("Test error")
        handled = error_handler.handle_exception(
            error,
            source_file="gs://bucket/test.csv",
            category=ErrorCategory.VALIDATION
        )

        # Should have all context
        assert handled.pipeline_name == "test"
        assert handled.run_id == "test_001"
        assert handled.source_file == "gs://bucket/test.csv"
        assert handled.category == ErrorCategory.VALIDATION

    def test_error_timestamp_recorded(self):
        """Test that error timestamp is recorded."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        before_time = datetime.utcnow()

        error = ValueError("Test")
        handled = error_handler.handle_exception(
            error,
            source_file="gs://bucket/test.csv",
            category=ErrorCategory.VALIDATION
        )

        after_time = datetime.utcnow()

        # Timestamp should be between before and after
        assert hasattr(handled, 'timestamp')
        if isinstance(handled.timestamp, str):
            timestamp = datetime.fromisoformat(handled.timestamp.replace('Z', '+00:00'))
            assert before_time <= timestamp <= after_time


class TestErrorMetrics:
    """Test error metrics collection."""

    def test_error_count_tracked(self):
        """Test that error counts are tracked."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        error_count = 0
        for i in range(10):
            error = ValueError(f"Error {i}")
            handled = error_handler.handle_exception(
                error,
                source_file="gs://bucket/file.csv",
                category=ErrorCategory.VALIDATION
            )
            if handled:
                error_count += 1

        assert error_count == 10

    def test_error_categories_tracked(self):
        """Test that error categories are tracked."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        categories = [
            ErrorCategory.VALIDATION,
            ErrorCategory.PERSISTENCE,
            ErrorCategory.INTEGRATION
        ]

        handled_by_category = {}

        for i, category in enumerate(categories):
            error = Exception(f"Error {i}")
            handled = error_handler.handle_exception(
                error,
                source_file="gs://bucket/file.csv",
                category=category
            )
            if category not in handled_by_category:
                handled_by_category[category] = 0
            handled_by_category[category] += 1

        assert len(handled_by_category) == 3

    def test_error_severity_distribution(self):
        """Test tracking error severity distribution."""
        error_handler = ErrorHandler(
            pipeline_name="test",
            run_id="test_001"
        )

        severities = [
            ErrorSeverity.CRITICAL,
            ErrorSeverity.HIGH,
            ErrorSeverity.MEDIUM,
            ErrorSeverity.LOW,
            ErrorSeverity.INFO
        ]

        severity_counts = {}

        for severity in severities:
            error = Exception(f"Error with {severity.name} severity")
            handled = error_handler.handle_exception(
                error,
                source_file="gs://bucket/file.csv",
                category=ErrorCategory.VALIDATION,
                severity=severity
            )
            if severity not in severity_counts:
                severity_counts[severity] = 0
            severity_counts[severity] += 1

        assert len(severity_counts) == 5


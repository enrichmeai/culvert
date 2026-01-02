"""Unit tests for ErrorClassifier."""

import pytest

from gdw_data_core.core.error_handling import (
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    RetryStrategy,
)


class TestErrorClassifier:
    """Tests for error classification logic."""

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


"""Unit tests for error types and enums."""

import pytest

from gcp_pipeline_builder.error_handling import (
    ErrorSeverity,
    ErrorCategory,
    RetryStrategy,
)


class TestErrorSeverity:
    """Test ErrorSeverity enum."""

    def test_severity_values(self):
        """Test all severity values exist."""
        assert ErrorSeverity.CRITICAL.value == "CRITICAL"
        assert ErrorSeverity.HIGH.value == "HIGH"
        assert ErrorSeverity.MEDIUM.value == "MEDIUM"
        assert ErrorSeverity.LOW.value == "LOW"
        assert ErrorSeverity.INFO.value == "INFO"


class TestErrorCategory:
    """Test ErrorCategory enum."""

    def test_category_values(self):
        """Test all category values exist."""
        assert ErrorCategory.VALIDATION.value == "VALIDATION"
        assert ErrorCategory.TRANSFORMATION.value == "TRANSFORMATION"
        assert ErrorCategory.INTEGRATION.value == "INTEGRATION"
        assert ErrorCategory.CONFIGURATION.value == "CONFIGURATION"
        assert ErrorCategory.RESOURCE.value == "RESOURCE"
        assert ErrorCategory.UNKNOWN.value == "UNKNOWN"


class TestRetryStrategy:
    """Test RetryStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values exist."""
        assert RetryStrategy.NO_RETRY.value == "NO_RETRY"
        assert RetryStrategy.IMMEDIATE.value == "IMMEDIATE"
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "EXPONENTIAL_BACKOFF"
        assert RetryStrategy.MANUAL_ONLY.value == "MANUAL_ONLY"


"""
Error handler for classification, routing, and retry logic.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import json
import logging
import time
import random
import traceback

from .types import ErrorSeverity, ErrorCategory, RetryStrategy
from .models import PipelineError, ErrorConfig
from .storage import ErrorStorageBackend

logger = logging.getLogger(__name__)


class ErrorClassifier:
    """Classifies exceptions into severity and category"""

    # Transient error types (can retry)
    TRANSIENT_ERRORS = frozenset({
        'TimeoutError', 'ConnectionError', 'BrokenPipeError',
        'OSError', 'IOError', 'TemporaryError', 'ServiceUnavailable',
        'TooManyRequests', 'ResourceExhausted'
    })

    # Validation error types (don't retry)
    VALIDATION_ERRORS = frozenset({
        'ValueError', 'TypeError', 'ValidationError', 'KeyError',
        'AttributeError', 'DataValidationError'
    })

    # Integration error types (retry with backoff)
    INTEGRATION_ERRORS = frozenset({
        'NotFound', 'AuthenticationError', 'PermissionError',
        'QuotaExceeded', 'ServiceError', 'ApiError'
    })

    @staticmethod
    def classify(exception: Exception) -> Tuple[ErrorSeverity, ErrorCategory, RetryStrategy]:
        """
        Classify an exception into severity, category, and retry strategy.

        Args:
            exception: The exception to classify

        Returns:
            Tuple of (severity, category, retry_strategy)
        """
        error_type = type(exception).__name__
        error_msg = str(exception).lower()

        # Check for specific patterns
        if any(pattern in error_msg for pattern in ('quota', 'rate limit', 'too many')):
            return (
                ErrorSeverity.HIGH,
                ErrorCategory.RESOURCE,
                RetryStrategy.EXPONENTIAL_BACKOFF
            )

        if any(pattern in error_msg for pattern in ('connection', 'timeout', 'unreachable')):
            return (
                ErrorSeverity.MEDIUM,
                ErrorCategory.INTEGRATION,
                RetryStrategy.EXPONENTIAL_BACKOFF
            )

        if any(pattern in error_msg for pattern in ('permission', 'forbidden', 'unauthorized')):
            return (
                ErrorSeverity.CRITICAL,
                ErrorCategory.CONFIGURATION,
                RetryStrategy.MANUAL_ONLY
            )

        if any(pattern in error_msg for pattern in ('not found', '404')):
            return (
                ErrorSeverity.MEDIUM,
                ErrorCategory.INTEGRATION,
                RetryStrategy.MANUAL_ONLY
            )

        # Check error type patterns
        if error_type in ErrorClassifier.VALIDATION_ERRORS:
            return (
                ErrorSeverity.MEDIUM,
                ErrorCategory.VALIDATION,
                RetryStrategy.NO_RETRY
            )

        if error_type in ErrorClassifier.TRANSIENT_ERRORS:
            return (
                ErrorSeverity.MEDIUM,
                ErrorCategory.INTEGRATION,
                RetryStrategy.EXPONENTIAL_BACKOFF
            )

        if error_type in ErrorClassifier.INTEGRATION_ERRORS:
            return (
                ErrorSeverity.HIGH,
                ErrorCategory.INTEGRATION,
                RetryStrategy.EXPONENTIAL_BACKOFF
            )

        # Default classification
        return (
            ErrorSeverity.HIGH,
            ErrorCategory.UNKNOWN,
            RetryStrategy.MANUAL_ONLY
        )


class RetryPolicy:
    """Manages retry logic with configurable strategies"""

    def __init__(self, config: Optional[ErrorConfig] = None):
        self.config = config if config is not None else ErrorConfig()

    def should_retry(self, error: PipelineError) -> bool:
        """Determine if error should be retried"""
        if error.retry_count >= self.config.max_retries:
            return False

        if error.retry_strategy in (RetryStrategy.NO_RETRY, RetryStrategy.MANUAL_ONLY):
            return False

        return True

    def calculate_backoff(self, error: PipelineError) -> Optional[int]:
        """Calculate delay in seconds before next retry"""
        if error.retry_strategy == RetryStrategy.IMMEDIATE:
            return 0

        if error.retry_strategy == RetryStrategy.NO_RETRY:
            return None

        if error.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.initial_retry_delay_seconds * (
                    self.config.backoff_multiplier ** error.retry_count
            )
        else:  # LINEAR_BACKOFF
            delay = self.config.initial_retry_delay_seconds * (error.retry_count + 1)

        # Cap at max delay
        delay = min(delay, self.config.max_retry_delay_seconds)

        # Add jitter if enabled
        if self.config.jitter_enabled:
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter

        return int(delay)

    def schedule_retry(self, error: PipelineError) -> Optional[datetime]:
        """Schedule next retry and return the scheduled time"""
        if not self.should_retry(error):
            return None

        delay = self.calculate_backoff(error)
        if delay is None:
            return None

        next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
        return next_retry


class ErrorHandler:
    """
    Centralized error handler for migration pipelines.

    Manages error classification, routing, retries, and storage.
    Integrates with monitoring and alerting systems.
    """

    def __init__(self,
                 pipeline_name: str,
                 run_id: str,
                 config: Optional[ErrorConfig] = None,
                 error_storage: Optional[ErrorStorageBackend] = None):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.config = config if config is not None else ErrorConfig()
        self.retry_policy = RetryPolicy(self.config)
        self.error_storage = error_storage
        self.errors: List[PipelineError] = []

    def handle_exception(self,
                         exception: Exception,
                         severity: Optional[ErrorSeverity] = None,
                         category: Optional[ErrorCategory] = None,
                         **kwargs) -> PipelineError:
        """
        Handle an exception and create error record.

        Args:
            exception: The exception to handle
            severity: Optional override for severity
            category: Optional override for category
            **kwargs: Additional error context (source_file, record_id, etc.)

        Returns:
            PipelineError record
        """
        # Classify error
        default_severity, default_category, retry_strategy = (
            ErrorClassifier.classify(exception)
        )

        # Use overrides if provided
        severity = severity if severity is not None else default_severity
        category = category if category is not None else default_category

        # Generate error ID
        error_id = f"{self.run_id}_{len(self.errors)}_{int(time.time() * 1000)}"

        # Create error record
        error = PipelineError(
            error_id=error_id,
            run_id=self.run_id,
            pipeline_name=self.pipeline_name,
            severity=severity,
            category=category,
            retry_strategy=retry_strategy,
            error_type=type(exception).__name__,
            error_message=str(exception),
            error_stacktrace=self._get_stacktrace(),
            **kwargs
        )

        self.errors.append(error)

        # Log error
        self._log_error(error)

        # Store if configured
        if self.error_storage:
            self.error_storage.store_error(error)

        # Alert if critical
        if severity == ErrorSeverity.CRITICAL and self.config.alert_on_critical:
            self._trigger_alert(error)

        return error

    def prepare_retry(self, error: PipelineError) -> bool:
        """
        Prepare error for retry.

        Returns:
            True if retry was scheduled, False if max retries exceeded
        """
        if not self.retry_policy.should_retry(error):
            return False

        error.retry_count += 1
        error.last_retry_timestamp = datetime.now(timezone.utc)
        error.next_retry_timestamp = self.retry_policy.schedule_retry(error)

        logger.info(
            "Scheduled retry %d for error %s at %s",
            error.retry_count,
            error.error_id,
            error.next_retry_timestamp
        )

        return True

    def get_critical_errors(self) -> List[PipelineError]:
        """Get all critical errors"""
        return [e for e in self.errors if e.severity == ErrorSeverity.CRITICAL]

    def get_retryable_errors(self) -> List[PipelineError]:
        """Get errors that can be retried"""
        return [
            e for e in self.errors
            if self.retry_policy.should_retry(e) and not e.resolved
        ]

    def get_unresolved_errors(self) -> List[PipelineError]:
        """Get all unresolved errors"""
        return [e for e in self.errors if not e.resolved]

    def mark_resolved(self, error_id: str, resolution_notes: Optional[str] = None):
        """Mark error as resolved"""
        for error in self.errors:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution_notes = resolution_notes
                logger.info("Marked error %s as resolved", error_id)
                return

        logger.warning("Error %s not found", error_id)

    def export_errors(self) -> str:
        """Export all errors as JSON"""
        return json.dumps([e.to_dict() for e in self.errors], default=str, indent=2)

    @staticmethod
    def _get_stacktrace() -> str:
        """Extract stacktrace from current exception context"""
        return traceback.format_exc()

    @staticmethod
    def _log_error(error: PipelineError):
        """Log error at appropriate level"""
        log_message = error.error_message

        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical("CRITICAL: %s", log_message)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error("ERROR: %s", log_message)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning("WARNING: %s", log_message)
        else:
            logger.info("INFO: %s", log_message)

    @staticmethod
    def _trigger_alert(error: PipelineError):
        """Trigger alert for critical errors (integration point)"""
        # This would integrate with monitoring system
        # For now, just log
        logger.critical("ALERT TRIGGERED: %s - %s", error.error_id, error.error_message)

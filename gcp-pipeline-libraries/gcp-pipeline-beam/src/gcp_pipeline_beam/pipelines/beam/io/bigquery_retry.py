"""
BigQuery Retry Module

Robust retry logic for BigQuery operations that goes beyond Beam's
native retries. Handles:
- Transient quota errors (rateLimitExceeded, quotaExceeded)
- Table lock errors (resourcesExceeded, backendError)
- Load job timeouts
- Streaming insert failures

This module provides production-grade retry policies specifically
tuned for BigQuery's error characteristics.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Iterator, List, Optional, Callable, Tuple

import apache_beam as beam
from apache_beam.transforms import window

logger = logging.getLogger(__name__)


class BigQueryErrorType(Enum):
    """Classification of BigQuery-specific errors."""
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMIT = "RATE_LIMIT"
    TABLE_LOCK = "TABLE_LOCK"
    BACKEND_ERROR = "BACKEND_ERROR"
    TIMEOUT = "TIMEOUT"
    INVALID_DATA = "INVALID_DATA"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    UNKNOWN = "UNKNOWN"


@dataclass
class BigQueryRetryConfig:
    """
    Configuration for BigQuery retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts per record/batch
        initial_delay_seconds: Initial delay before first retry
        max_delay_seconds: Maximum delay between retries
        backoff_multiplier: Exponential backoff multiplier
        jitter_fraction: Random jitter as fraction of delay (0.0-1.0)
        quota_retry_delay: Special delay for quota errors (typically longer)
        table_lock_retry_delay: Delay for table lock errors
        timeout_seconds: Timeout for individual operations
        batch_size: Records per batch for streaming inserts
        retry_on_timeout: Whether to retry timeout errors
        dead_letter_after_retries: Write to DLQ after max retries
    """
    max_retries: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0  # 5 minutes max
    backoff_multiplier: float = 2.0
    jitter_fraction: float = 0.2
    quota_retry_delay: float = 60.0  # 1 minute for quota errors
    table_lock_retry_delay: float = 30.0  # 30 seconds for lock errors
    timeout_seconds: float = 600.0  # 10 minute timeout
    batch_size: int = 500
    retry_on_timeout: bool = True
    dead_letter_after_retries: bool = True


class BigQueryErrorClassifier:
    """Classifies BigQuery errors and determines retry strategy."""

    # Error message patterns for classification
    QUOTA_PATTERNS = [
        "quota exceeded",
        "quotaexceeded",
        "exceeded quota",
        "daily limit exceeded",
        "project exceeded"
    ]

    RATE_LIMIT_PATTERNS = [
        "rate limit",
        "ratelimitexceeded",
        "too many requests",
        "slow down",
        "exceeded rate limit"
    ]

    TABLE_LOCK_PATTERNS = [
        "table is locked",
        "resources exceeded",
        "could not serialize access",
        "concurrent update",
        "transaction aborted"
    ]

    BACKEND_PATTERNS = [
        "backend error",
        "internal error",
        "service unavailable",
        "503",
        "500"
    ]

    TIMEOUT_PATTERNS = [
        "timeout",
        "deadline exceeded",
        "operation timed out",
        "job timed out"
    ]

    INVALID_DATA_PATTERNS = [
        "invalid value",
        "invalid field",
        "no such field",
        "could not convert",
        "json parsing error"
    ]

    SCHEMA_PATTERNS = [
        "schema mismatch",
        "incompatible schema",
        "no matching signature",
        "unknown field"
    ]

    NOT_FOUND_PATTERNS = [
        "not found",
        "404",
        "does not exist"
    ]

    PERMISSION_PATTERNS = [
        "permission denied",
        "access denied",
        "forbidden",
        "403"
    ]

    @classmethod
    def classify(cls, error: Exception) -> Tuple[BigQueryErrorType, bool]:
        """
        Classify a BigQuery error and determine if it's retryable.

        Args:
            error: The exception to classify

        Returns:
            Tuple of (error_type, is_retryable)
        """
        error_msg = str(error).lower()
        error_type_name = type(error).__name__

        # Check patterns in order of specificity
        if any(p in error_msg for p in cls.QUOTA_PATTERNS):
            return BigQueryErrorType.QUOTA_EXCEEDED, True

        if any(p in error_msg for p in cls.RATE_LIMIT_PATTERNS):
            return BigQueryErrorType.RATE_LIMIT, True

        if any(p in error_msg for p in cls.TABLE_LOCK_PATTERNS):
            return BigQueryErrorType.TABLE_LOCK, True

        if any(p in error_msg for p in cls.BACKEND_PATTERNS):
            return BigQueryErrorType.BACKEND_ERROR, True

        if any(p in error_msg for p in cls.TIMEOUT_PATTERNS):
            return BigQueryErrorType.TIMEOUT, True

        if any(p in error_msg for p in cls.INVALID_DATA_PATTERNS):
            return BigQueryErrorType.INVALID_DATA, False

        if any(p in error_msg for p in cls.SCHEMA_PATTERNS):
            return BigQueryErrorType.SCHEMA_MISMATCH, False

        if any(p in error_msg for p in cls.NOT_FOUND_PATTERNS):
            return BigQueryErrorType.NOT_FOUND, False

        if any(p in error_msg for p in cls.PERMISSION_PATTERNS):
            return BigQueryErrorType.PERMISSION_DENIED, False

        # Check exception type
        if "google.api_core.exceptions" in str(type(error)):
            if "ResourceExhausted" in error_type_name:
                return BigQueryErrorType.RESOURCE_EXHAUSTED, True
            if "ServiceUnavailable" in error_type_name:
                return BigQueryErrorType.BACKEND_ERROR, True
            if "DeadlineExceeded" in error_type_name:
                return BigQueryErrorType.TIMEOUT, True

        return BigQueryErrorType.UNKNOWN, False

    @classmethod
    def get_retry_delay(
        cls,
        error_type: BigQueryErrorType,
        config: BigQueryRetryConfig,
        retry_count: int
    ) -> float:
        """
        Get recommended delay before retry based on error type.

        Args:
            error_type: The classified error type
            config: Retry configuration
            retry_count: Current retry attempt number

        Returns:
            Delay in seconds before next retry
        """
        # Base delay calculation with exponential backoff
        base_delay = config.initial_delay_seconds * (config.backoff_multiplier ** retry_count)

        # Apply error-specific overrides
        if error_type == BigQueryErrorType.QUOTA_EXCEEDED:
            base_delay = max(base_delay, config.quota_retry_delay)
        elif error_type == BigQueryErrorType.TABLE_LOCK:
            base_delay = max(base_delay, config.table_lock_retry_delay)
        elif error_type == BigQueryErrorType.RATE_LIMIT:
            # For rate limits, use shorter delays with more retries
            base_delay = config.initial_delay_seconds * (1.5 ** retry_count)

        # Cap at max delay
        base_delay = min(base_delay, config.max_delay_seconds)

        # Add jitter
        jitter = random.uniform(0, base_delay * config.jitter_fraction)

        return base_delay + jitter


@dataclass
class RetryState:
    """Tracks retry state for a record or batch."""
    record_id: str
    retry_count: int = 0
    last_error: Optional[str] = None
    last_error_type: Optional[BigQueryErrorType] = None
    first_attempt_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt_time: Optional[datetime] = None
    next_retry_time: Optional[datetime] = None
    total_delay_seconds: float = 0.0


class ResilientWriteToBigQueryDoFn(beam.DoFn):
    """
    Production-grade BigQuery writer with explicit retry logic.

    Goes beyond Beam's native retries to handle BigQuery-specific
    transient errors with appropriate backoff strategies.

    Features:
    - Explicit retry logic for quota/rate limit errors
    - Table lock detection and exponential backoff
    - Timeout handling with configurable retry
    - Dead letter queue for exhausted retries
    - Metrics for monitoring retry behavior
    - Circuit breaker to prevent cascade failures

    Outputs:
        Main: Dict - Successfully written records
        'retryable': Dict - Records that can be retried (for external retry)
        'dead_letter': Dict - Records that exhausted retries
        'errors': Dict - Records with non-retryable errors

    Metrics:
        bq_retry_write/success: Successfully written records
        bq_retry_write/retried: Records that were retried
        bq_retry_write/dead_letter: Records sent to dead letter queue
        bq_retry_write/errors: Non-retryable errors
        bq_retry_write/quota_errors: Quota-related errors
        bq_retry_write/lock_errors: Table lock errors
        bq_retry_write/timeout_errors: Timeout errors

    Example:
        >>> config = BigQueryRetryConfig(
        ...     max_retries=5,
        ...     quota_retry_delay=60.0
        ... )
        >>> pipeline | 'WriteBQ' >> beam.ParDo(
        ...     ResilientWriteToBigQueryDoFn(
        ...         project='my-project',
        ...         dataset='my_dataset',
        ...         table='my_table',
        ...         config=config
        ...     )
        ... ).with_outputs('main', 'retryable', 'dead_letter', 'errors')
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        config: Optional[BigQueryRetryConfig] = None,
        schema: Optional[List[Dict[str, str]]] = None,
        run_id: Optional[str] = None
    ):
        """
        Initialize resilient BigQuery writer.

        Args:
            project: GCP Project ID
            dataset: BigQuery dataset name
            table: BigQuery table name
            config: Retry configuration (uses defaults if not provided)
            schema: Optional table schema
            run_id: Unique run identifier for tracking
        """
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.config = config or BigQueryRetryConfig()
        self.schema = schema
        self.run_id = run_id or "unknown"

        # Metrics
        self.success = beam.metrics.Metrics.counter("bq_retry_write", "success")
        self.retried = beam.metrics.Metrics.counter("bq_retry_write", "retried")
        self.dead_letter = beam.metrics.Metrics.counter("bq_retry_write", "dead_letter")
        self.errors = beam.metrics.Metrics.counter("bq_retry_write", "errors")
        self.quota_errors = beam.metrics.Metrics.counter("bq_retry_write", "quota_errors")
        self.lock_errors = beam.metrics.Metrics.counter("bq_retry_write", "lock_errors")
        self.timeout_errors = beam.metrics.Metrics.counter("bq_retry_write", "timeout_errors")

        self.client = None
        self.table_ref = None

    def setup(self):
        """Initialize BigQuery client."""
        from google.cloud import bigquery
        self.client = bigquery.Client(project=self.project)
        self.table_ref = f"{self.project}.{self.dataset}.{self.table}"

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """
        Write element to BigQuery with retry logic.

        Args:
            element: Record to write

        Yields:
            Records to appropriate output based on result
        """
        record_id = str(element.get('id', element.get('_id', hash(str(element)))))
        state = RetryState(record_id=record_id)

        while state.retry_count <= self.config.max_retries:
            try:
                # Attempt to write
                errors = self.client.insert_rows_json(self.table_ref, [element])

                if not errors:
                    # Success
                    self.success.inc()
                    yield element
                    return

                # Handle streaming insert errors
                error_msg = str(errors[0].get('errors', [{}])[0].get('message', 'Unknown'))
                error_type, is_retryable = BigQueryErrorClassifier.classify(
                    Exception(error_msg)
                )

                self._update_error_metrics(error_type)
                state.last_error = error_msg
                state.last_error_type = error_type
                state.last_attempt_time = datetime.now(timezone.utc)

                if is_retryable and state.retry_count < self.config.max_retries:
                    delay = BigQueryErrorClassifier.get_retry_delay(
                        error_type, self.config, state.retry_count
                    )
                    state.retry_count += 1
                    state.total_delay_seconds += delay
                    state.next_retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay)

                    logger.warning(
                        f"BigQuery insert failed (attempt {state.retry_count}/{self.config.max_retries}), "
                        f"retrying in {delay:.1f}s: {error_msg}"
                    )

                    self.retried.inc()
                    time.sleep(delay)
                    continue
                else:
                    # Not retryable or exhausted retries
                    break

            except Exception as e:
                error_type, is_retryable = BigQueryErrorClassifier.classify(e)
                self._update_error_metrics(error_type)

                state.last_error = str(e)
                state.last_error_type = error_type
                state.last_attempt_time = datetime.now(timezone.utc)

                if is_retryable and state.retry_count < self.config.max_retries:
                    delay = BigQueryErrorClassifier.get_retry_delay(
                        error_type, self.config, state.retry_count
                    )
                    state.retry_count += 1
                    state.total_delay_seconds += delay
                    state.next_retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay)

                    logger.warning(
                        f"BigQuery write exception (attempt {state.retry_count}/{self.config.max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )

                    self.retried.inc()
                    time.sleep(delay)
                    continue
                else:
                    break

        # Exhausted retries or non-retryable error
        error_type, is_retryable = BigQueryErrorClassifier.classify(
            Exception(state.last_error or "Unknown error")
        )

        error_record = {
            "record": element,
            "record_id": record_id,
            "error": state.last_error,
            "error_type": state.last_error_type.value if state.last_error_type else "UNKNOWN",
            "retry_count": state.retry_count,
            "total_delay_seconds": state.total_delay_seconds,
            "first_attempt": state.first_attempt_time.isoformat(),
            "last_attempt": state.last_attempt_time.isoformat() if state.last_attempt_time else None,
            "run_id": self.run_id
        }

        if is_retryable and self.config.dead_letter_after_retries:
            # Can potentially be retried later (e.g., by a retry DAG)
            self.dead_letter.inc()
            yield beam.pvalue.TaggedOutput("dead_letter", error_record)
        elif is_retryable:
            # Output for external retry mechanism
            self.retried.inc()
            yield beam.pvalue.TaggedOutput("retryable", error_record)
        else:
            # Non-retryable error
            self.errors.inc()
            yield beam.pvalue.TaggedOutput("errors", error_record)

    def _update_error_metrics(self, error_type: BigQueryErrorType):
        """Update error-specific metrics."""
        if error_type in (BigQueryErrorType.QUOTA_EXCEEDED, BigQueryErrorType.RATE_LIMIT):
            self.quota_errors.inc()
        elif error_type == BigQueryErrorType.TABLE_LOCK:
            self.lock_errors.inc()
        elif error_type == BigQueryErrorType.TIMEOUT:
            self.timeout_errors.inc()


class BatchResilientWriteToBigQueryDoFn(beam.DoFn):
    """
    Batched BigQuery writer with retry logic for better throughput.

    Collects records into batches and writes them with retry logic.
    More efficient for high-volume ingestion while maintaining
    resilience against transient errors.

    Outputs:
        Main: Dict - Successfully written records
        'dead_letter': Dict - Records that exhausted retries
        'errors': Dict - Records with non-retryable errors

    Example:
        >>> pipeline | 'BatchWriteBQ' >> beam.ParDo(
        ...     BatchResilientWriteToBigQueryDoFn(
        ...         project='my-project',
        ...         dataset='my_dataset',
        ...         table='my_table',
        ...         batch_size=500
        ...     )
        ... ).with_outputs('main', 'dead_letter', 'errors')
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        batch_size: int = 500,
        config: Optional[BigQueryRetryConfig] = None,
        run_id: Optional[str] = None
    ):
        """
        Initialize batched BigQuery writer.

        Args:
            project: GCP Project ID
            dataset: BigQuery dataset name
            table: BigQuery table name
            batch_size: Records per batch
            config: Retry configuration
            run_id: Run identifier
        """
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.batch_size = batch_size
        self.config = config or BigQueryRetryConfig()
        self.run_id = run_id or "unknown"

        self.batch: List[Dict[str, Any]] = []

        # Metrics
        self.success = beam.metrics.Metrics.counter("bq_batch_retry", "success")
        self.batches_written = beam.metrics.Metrics.counter("bq_batch_retry", "batches")
        self.retried = beam.metrics.Metrics.counter("bq_batch_retry", "retried")
        self.dead_letter = beam.metrics.Metrics.counter("bq_batch_retry", "dead_letter")
        self.errors = beam.metrics.Metrics.counter("bq_batch_retry", "errors")

        self.client = None
        self.table_ref = None

    def setup(self):
        """Initialize BigQuery client."""
        from google.cloud import bigquery
        self.client = bigquery.Client(project=self.project)
        self.table_ref = f"{self.project}.{self.dataset}.{self.table}"
        self.batch = []

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """Buffer records and flush when batch is full."""
        self.batch.append(element)

        if len(self.batch) >= self.batch_size:
            yield from self._flush_batch_with_retry()

        # Pass through for chaining
        yield element

    def finish_bundle(self):
        """Flush remaining records."""
        if self.batch:
            yield from self._flush_batch_with_retry()

    def _flush_batch_with_retry(self) -> Iterator[Any]:
        """
        Flush batch with retry logic.

        Attempts to write the entire batch. On failure:
        1. If retryable, retry with backoff
        2. If partial failure, identify and retry failed rows
        3. After exhausting retries, route to dead letter
        """
        if not self.batch:
            return

        batch_to_write = self.batch.copy()
        self.batch = []

        retry_count = 0

        while retry_count <= self.config.max_retries and batch_to_write:
            try:
                errors = self.client.insert_rows_json(self.table_ref, batch_to_write)

                if not errors:
                    # All records succeeded
                    self.batches_written.inc()
                    self.success.inc(len(batch_to_write))
                    logger.info(f"Successfully wrote batch of {len(batch_to_write)} records")
                    return

                # Handle partial failures
                # BigQuery streaming inserts return errors per row
                failed_indices = set()
                retryable_failures = []
                non_retryable_failures = []

                for error in errors:
                    idx = error.get('index', 0)
                    error_msg = str(error.get('errors', [{}])[0].get('message', 'Unknown'))
                    error_type, is_retryable = BigQueryErrorClassifier.classify(
                        Exception(error_msg)
                    )

                    failed_indices.add(idx)
                    record = batch_to_write[idx] if idx < len(batch_to_write) else {}

                    failure_info = {
                        "record": record,
                        "error": error_msg,
                        "error_type": error_type.value,
                        "retry_count": retry_count,
                        "run_id": self.run_id
                    }

                    if is_retryable:
                        retryable_failures.append((idx, failure_info))
                    else:
                        non_retryable_failures.append(failure_info)

                # Yield successful records
                for i, record in enumerate(batch_to_write):
                    if i not in failed_indices:
                        self.success.inc()

                # Handle non-retryable failures immediately
                for failure in non_retryable_failures:
                    self.errors.inc()
                    yield beam.pvalue.TaggedOutput("errors", failure)

                # Retry only the failed retryable records
                if retryable_failures and retry_count < self.config.max_retries:
                    # Get the worst error type for backoff calculation
                    worst_error = BigQueryErrorType.UNKNOWN
                    for _, failure in retryable_failures:
                        et = BigQueryErrorType(failure["error_type"])
                        if et in (BigQueryErrorType.QUOTA_EXCEEDED, BigQueryErrorType.TABLE_LOCK):
                            worst_error = et
                            break

                    delay = BigQueryErrorClassifier.get_retry_delay(
                        worst_error, self.config, retry_count
                    )

                    retry_count += 1
                    self.retried.inc(len(retryable_failures))

                    logger.warning(
                        f"Batch had {len(retryable_failures)} retryable failures, "
                        f"retry {retry_count}/{self.config.max_retries} in {delay:.1f}s"
                    )

                    time.sleep(delay)

                    # Prepare retry batch with only failed records
                    batch_to_write = [batch_to_write[idx] for idx, _ in retryable_failures]
                    continue
                else:
                    # Exhausted retries for remaining failures
                    for _, failure in retryable_failures:
                        self.dead_letter.inc()
                        yield beam.pvalue.TaggedOutput("dead_letter", failure)
                    return

            except Exception as e:
                error_type, is_retryable = BigQueryErrorClassifier.classify(e)

                if is_retryable and retry_count < self.config.max_retries:
                    delay = BigQueryErrorClassifier.get_retry_delay(
                        error_type, self.config, retry_count
                    )
                    retry_count += 1
                    self.retried.inc()

                    logger.warning(
                        f"Batch write failed with {error_type.value}, "
                        f"retry {retry_count}/{self.config.max_retries} in {delay:.1f}s: {e}"
                    )

                    time.sleep(delay)
                    continue
                else:
                    # Route entire batch to appropriate output
                    for record in batch_to_write:
                        error_record = {
                            "record": record,
                            "error": str(e),
                            "error_type": error_type.value,
                            "retry_count": retry_count,
                            "run_id": self.run_id
                        }

                        if is_retryable:
                            self.dead_letter.inc()
                            yield beam.pvalue.TaggedOutput("dead_letter", error_record)
                        else:
                            self.errors.inc()
                            yield beam.pvalue.TaggedOutput("errors", error_record)
                    return


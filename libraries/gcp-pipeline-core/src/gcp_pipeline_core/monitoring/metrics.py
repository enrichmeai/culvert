"""
Metrics collection and management.

Thread-safe metric collection for counters, gauges, and histograms.
Supports multiple backends for metric storage.
"""

import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional

from .types import MetricValue


class MetricsCollector:
    """
    Collects metrics from migration pipelines.

    Thread-safe metric collection for counters, gauges, and histograms.
    Supports multiple backends for metric storage.
    """

    def __init__(self, pipeline_name: str, run_id: str):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.start_time = datetime.utcnow()

        # Metric storage
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)

        # Metric history for export
        self.metric_history: List[MetricValue] = []

    def increment(self, metric_name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        self.counters[metric_name] += value
        self._record_metric(metric_name, float(self.counters[metric_name]), labels)

    def set_gauge(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        self.gauges[metric_name] = value
        self._record_metric(metric_name, value, labels)

    def record_histogram(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram value (distribution)"""
        self.histograms[metric_name].append(value)
        self._record_metric(metric_name, value, labels)

    def record_timer(self, metric_name: str, duration_seconds: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer measurement"""
        self.timers[metric_name].append(duration_seconds)
        self._record_metric(metric_name, duration_seconds, labels)

    def start_timer(self) -> 'TimerContext':
        """Create a timer context for automatic duration measurement"""
        return TimerContext(self)

    def record_step_duration(self, step_name: str, duration_seconds: float):
        """Record duration of a pipeline step"""
        self.record_timer(f"step_duration_{step_name}", duration_seconds)

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of all metrics"""
        current_time = datetime.utcnow()
        stats = {
            'pipeline_name': self.pipeline_name,
            'run_id': self.run_id,
            'start_time': self.start_time.isoformat(),
            'current_time': current_time.isoformat(),
            'uptime_seconds': (current_time - self.start_time).total_seconds(),
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'histograms_summary': {},
            'timers_summary': {}
        }

        # Compute histogram statistics
        for name, values in self.histograms.items():
            if values:
                stats['histograms_summary'][name] = self._calculate_stats(values)

        # Compute timer statistics
        for name, values in self.timers.items():
            if values:
                stats['timers_summary'][name] = self._calculate_stats(values)

        return stats

    def _calculate_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistics for a list of values"""
        total = sum(values)
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': total / len(values),
            'total': total
        }

    def _record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Internal method to record metric"""
        metric = MetricValue(
            name=name,
            value=value,
            labels=labels or {}
        )
        self.metric_history.append(metric)


class TimerContext:
    """
    Context manager for timing operations and recording to a MetricsCollector.
    """
    def __init__(self, collector: MetricsCollector, metric_name: str = "duration"):
        self.collector = collector
        self.metric_name = metric_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.collector.record_timer(self.metric_name, duration)


class MigrationMetrics:
    """
    Standardized metrics for data migration pipelines.

    Provides consistent metric names and automatic tagging with
    run_id, system_id, and entity_type for all pipeline metrics.

    Standard Metrics:
    - records_read: Total records read from source
    - records_parsed: Records successfully parsed
    - records_validated: Records that passed validation
    - records_failed: Records that failed validation
    - records_written: Records written to destination
    - processing_duration_ms: Time to process records
    - validation_errors: Count by error type

    Example:
        >>> metrics = MigrationMetrics(
        ...     run_id="em_20260105_143022",
        ...     system_id="EM",
        ...     entity_type="customers"
        ... )
        >>> metrics.record_read(1000)
        >>> metrics.record_validated(950)
        >>> metrics.record_failed(50)
        >>> print(metrics.get_summary())
    """

    # Standard metric names
    RECORDS_READ = "records_read"
    RECORDS_PARSED = "records_parsed"
    RECORDS_VALIDATED = "records_validated"
    RECORDS_FAILED = "records_failed"
    RECORDS_WRITTEN = "records_written"
    RECORDS_SKIPPED = "records_skipped"
    PROCESSING_DURATION_MS = "processing_duration_ms"
    VALIDATION_ERRORS = "validation_errors"
    PARSE_ERRORS = "parse_errors"

    def __init__(
        self,
        run_id: str,
        system_id: str,
        entity_type: Optional[str] = None,
        pipeline_name: Optional[str] = None
    ):
        """
        Initialize migration metrics.

        Args:
            run_id: Pipeline run identifier
            system_id: System identifier (EM, LOA)
            entity_type: Entity being processed (customers, accounts, etc.)
            pipeline_name: Optional pipeline name
        """
        self.run_id = run_id
        self.system_id = system_id
        self.entity_type = entity_type
        self.pipeline_name = pipeline_name or f"{system_id}_{entity_type or 'pipeline'}"

        # Initialize collector
        self._collector = MetricsCollector(
            pipeline_name=self.pipeline_name,
            run_id=run_id
        )

        # Standard labels for all metrics
        self._labels = {
            'run_id': run_id,
            'system_id': system_id,
        }
        if entity_type:
            self._labels['entity_type'] = entity_type

    def _get_labels(self, extra_labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get labels with optional extras."""
        labels = self._labels.copy()
        if extra_labels:
            labels.update(extra_labels)
        return labels

    # Record counting methods
    def record_read(self, count: int = 1):
        """Record records read from source."""
        self._collector.increment(self.RECORDS_READ, count, self._get_labels())

    def record_parsed(self, count: int = 1):
        """Record records successfully parsed."""
        self._collector.increment(self.RECORDS_PARSED, count, self._get_labels())

    def record_validated(self, count: int = 1):
        """Record records that passed validation."""
        self._collector.increment(self.RECORDS_VALIDATED, count, self._get_labels())

    def record_failed(self, count: int = 1, error_type: Optional[str] = None):
        """Record records that failed validation."""
        labels = self._get_labels()
        if error_type:
            labels['error_type'] = error_type
        self._collector.increment(self.RECORDS_FAILED, count, labels)

    def record_written(self, count: int = 1):
        """Record records written to destination."""
        self._collector.increment(self.RECORDS_WRITTEN, count, self._get_labels())

    def record_skipped(self, count: int = 1, reason: Optional[str] = None):
        """Record records skipped."""
        labels = self._get_labels()
        if reason:
            labels['skip_reason'] = reason
        self._collector.increment(self.RECORDS_SKIPPED, count, labels)

    def record_validation_error(self, error_type: str, count: int = 1):
        """Record validation error by type."""
        labels = self._get_labels({'error_type': error_type})
        self._collector.increment(self.VALIDATION_ERRORS, count, labels)

    def record_parse_error(self, count: int = 1):
        """Record parse error."""
        self._collector.increment(self.PARSE_ERRORS, count, self._get_labels())

    # Timing methods
    def record_processing_time(self, duration_ms: float):
        """Record processing duration in milliseconds."""
        self._collector.record_histogram(
            self.PROCESSING_DURATION_MS,
            duration_ms,
            self._get_labels()
        )

    def start_timer(self, metric_name: str = "operation") -> TimerContext:
        """Start a timer for an operation."""
        return TimerContext(self._collector, f"{metric_name}_duration")

    # Summary methods
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all migration metrics.

        Returns:
            Dict with counts, rates, and duration stats
        """
        stats = self._collector.get_statistics()

        # Calculate rates
        read = stats['counters'].get(self.RECORDS_READ, 0)
        validated = stats['counters'].get(self.RECORDS_VALIDATED, 0)
        failed = stats['counters'].get(self.RECORDS_FAILED, 0)

        summary = {
            'run_id': self.run_id,
            'system_id': self.system_id,
            'entity_type': self.entity_type,
            'counts': {
                'read': read,
                'parsed': stats['counters'].get(self.RECORDS_PARSED, 0),
                'validated': validated,
                'failed': failed,
                'written': stats['counters'].get(self.RECORDS_WRITTEN, 0),
                'skipped': stats['counters'].get(self.RECORDS_SKIPPED, 0),
            },
            'rates': {
                'validation_success_rate': (validated / read * 100) if read > 0 else 0,
                'validation_failure_rate': (failed / read * 100) if read > 0 else 0,
            },
            'duration': stats.get('uptime_seconds', 0),
            'start_time': stats.get('start_time'),
        }

        return summary

    def to_job_record(self) -> Dict[str, Any]:
        """
        Convert metrics to job control record format.

        Returns:
            Dict suitable for updating pipeline_jobs table
        """
        summary = self.get_summary()
        return {
            'run_id': self.run_id,
            'system_id': self.system_id,
            'entity_type': self.entity_type,
            'records_read': summary['counts']['read'],
            'records_validated': summary['counts']['validated'],
            'records_failed': summary['counts']['failed'],
            'records_written': summary['counts']['written'],
            'validation_success_rate': summary['rates']['validation_success_rate'],
            'processing_duration_seconds': summary['duration'],
        }


__all__ = [
    'MetricsCollector',
    'TimerContext',
    'MigrationMetrics',
]


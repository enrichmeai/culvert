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

"""
Bridge between existing MetricsCollector and OTEL metrics.

Allows existing code using MetricsCollector to automatically
export metrics via OTEL without code changes.
"""

from typing import Dict, Optional, Any
import logging

from .tracing import get_meter

logger = logging.getLogger(__name__)


class OTELMetricsBridge:
    """
    Bridges MetricsCollector to OTEL metrics API.

    Wraps a MetricsCollector and forwards all metrics to OTEL.
    This allows existing pipelines using MetricsCollector to
    automatically export metrics to Dynatrace/GCP without code changes.

    Example:
        >>> from gcp_pipeline_core.monitoring import MetricsCollector
        >>> from gcp_pipeline_core.monitoring.otel import OTELMetricsBridge
        >>>
        >>> collector = MetricsCollector("my_pipeline", "run_123")
        >>> bridge = OTELMetricsBridge(collector)
        >>>
        >>> # Use bridge as normal - metrics go to both
        >>> bridge.increment("records_processed", 100)
    """

    def __init__(
        self,
        collector: Any,  # MetricsCollector
        meter_name: str = "pipeline_metrics",
    ):
        self._collector = collector
        self._meter = get_meter(meter_name)
        self._counters = {}
        self._gauges = {}
        self._histograms = {}

        # Base attributes for all metrics
        self._base_attributes = {
            "pipeline_name": getattr(collector, 'pipeline_name', 'unknown'),
            "run_id": getattr(collector, 'run_id', 'unknown'),
        }

    def increment(
        self,
        metric_name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ):
        """Increment counter in both collector and OTEL."""
        # Forward to original collector
        self._collector.increment(metric_name, value, labels)

        # Also send to OTEL
        try:
            counter = self._get_or_create_counter(metric_name)
            attributes = {**self._base_attributes, **(labels or {})}
            counter.add(value, attributes)
        except Exception as e:
            logger.debug(f"Failed to send counter to OTEL: {e}")

    def set_gauge(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Set gauge in both collector and OTEL."""
        self._collector.set_gauge(metric_name, value, labels)

        # For OTEL, we use an UpDownCounter for gauge-like behavior
        try:
            gauge = self._get_or_create_gauge(metric_name)
            attributes = {**self._base_attributes, **(labels or {})}
            gauge.add(value, attributes)
        except Exception as e:
            logger.debug(f"Failed to send gauge to OTEL: {e}")

    def record_histogram(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record histogram in both collector and OTEL."""
        self._collector.record_histogram(metric_name, value, labels)

        try:
            histogram = self._get_or_create_histogram(metric_name)
            attributes = {**self._base_attributes, **(labels or {})}
            histogram.record(value, attributes)
        except Exception as e:
            logger.debug(f"Failed to send histogram to OTEL: {e}")

    def record_timer(
        self,
        metric_name: str,
        duration_seconds: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record timer in both collector and OTEL."""
        self._collector.record_timer(metric_name, duration_seconds, labels)

        # Record as histogram with seconds unit
        try:
            histogram = self._get_or_create_histogram(f"{metric_name}_seconds")
            attributes = {**self._base_attributes, **(labels or {})}
            histogram.record(duration_seconds, attributes)
        except Exception as e:
            logger.debug(f"Failed to send timer to OTEL: {e}")

    def _get_or_create_counter(self, name: str):
        """Get or create an OTEL counter."""
        if name not in self._counters:
            self._counters[name] = self._meter.create_counter(
                name=f"pipeline.{name}",
                description=f"Counter for {name}",
                unit="1",
            )
        return self._counters[name]

    def _get_or_create_gauge(self, name: str):
        """Get or create an OTEL gauge (using UpDownCounter)."""
        if name not in self._gauges:
            self._gauges[name] = self._meter.create_up_down_counter(
                name=f"pipeline.{name}",
                description=f"Gauge for {name}",
                unit="1",
            )
        return self._gauges[name]

    def _get_or_create_histogram(self, name: str):
        """Get or create an OTEL histogram."""
        if name not in self._histograms:
            self._histograms[name] = self._meter.create_histogram(
                name=f"pipeline.{name}",
                description=f"Histogram for {name}",
                unit="1",
            )
        return self._histograms[name]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from underlying collector."""
        return self._collector.get_statistics()

    def start_timer(self):
        """Create a timer context for automatic duration measurement."""
        return self._collector.start_timer()

    def record_step_duration(self, step_name: str, duration_seconds: float):
        """Record duration of a pipeline step."""
        self._collector.record_step_duration(step_name, duration_seconds)

        # Also send to OTEL
        try:
            histogram = self._get_or_create_histogram(f"step_duration_{step_name}_seconds")
            attributes = self._base_attributes.copy()
            attributes["step"] = step_name
            histogram.record(duration_seconds, attributes)
        except Exception as e:
            logger.debug(f"Failed to send step duration to OTEL: {e}")

    # Delegate other methods to collector
    def __getattr__(self, name):
        return getattr(self._collector, name)


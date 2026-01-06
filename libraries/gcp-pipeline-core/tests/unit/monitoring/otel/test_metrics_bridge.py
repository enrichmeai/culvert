"""Tests for OTEL metrics bridge."""

import pytest
from unittest.mock import MagicMock

from gcp_pipeline_core.monitoring.otel import OTELMetricsBridge
from gcp_pipeline_core.monitoring.otel.tracing import shutdown_otel
from gcp_pipeline_core.monitoring.otel.provider import reset_provider


class MockMetricsCollector:
    """Mock MetricsCollector for testing."""

    def __init__(self, pipeline_name: str, run_id: str):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.counters = {}
        self.gauges = {}
        self.histograms = {}
        self.timers = {}

    def increment(self, metric_name, value=1, labels=None):
        self.counters[metric_name] = self.counters.get(metric_name, 0) + value

    def set_gauge(self, metric_name, value, labels=None):
        self.gauges[metric_name] = value

    def record_histogram(self, metric_name, value, labels=None):
        if metric_name not in self.histograms:
            self.histograms[metric_name] = []
        self.histograms[metric_name].append(value)

    def record_timer(self, metric_name, duration_seconds, labels=None):
        if metric_name not in self.timers:
            self.timers[metric_name] = []
        self.timers[metric_name].append(duration_seconds)

    def record_step_duration(self, step_name, duration_seconds):
        self.record_timer(f"step_duration_{step_name}", duration_seconds)

    def start_timer(self):
        return MagicMock()

    def get_statistics(self):
        return {
            "counters": self.counters,
            "gauges": self.gauges,
        }


class TestOTELMetricsBridge:
    """Tests for OTELMetricsBridge."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        shutdown_otel()
        reset_provider()

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_otel()
        reset_provider()

    def test_increment_forwards_to_collector(self):
        """Test increment forwards to underlying collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.increment("records_processed", 100)

        assert collector.counters["records_processed"] == 100

    def test_increment_multiple_times(self):
        """Test increment multiple times accumulates."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.increment("records_processed", 50)
        bridge.increment("records_processed", 50)

        assert collector.counters["records_processed"] == 100

    def test_set_gauge_forwards_to_collector(self):
        """Test set_gauge forwards to underlying collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.set_gauge("current_batch_size", 500)

        assert collector.gauges["current_batch_size"] == 500

    def test_record_histogram_forwards_to_collector(self):
        """Test record_histogram forwards to underlying collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.record_histogram("record_size", 1024)

        assert collector.histograms["record_size"] == [1024]

    def test_record_timer_forwards_to_collector(self):
        """Test record_timer forwards to underlying collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.record_timer("processing_time", 1.5)

        assert collector.timers["processing_time"] == [1.5]

    def test_get_statistics_returns_collector_stats(self):
        """Test get_statistics returns underlying collector stats."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.increment("test", 10)
        stats = bridge.get_statistics()

        assert stats["counters"]["test"] == 10

    def test_start_timer_delegates_to_collector(self):
        """Test start_timer delegates to collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        timer = bridge.start_timer()
        assert timer is not None

    def test_record_step_duration_forwards_to_collector(self):
        """Test record_step_duration forwards to collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        bridge.record_step_duration("validation", 2.5)

        assert collector.timers["step_duration_validation"] == [2.5]

    def test_base_attributes_set_from_collector(self):
        """Test base attributes are extracted from collector."""
        collector = MockMetricsCollector("test_pipeline", "run_123")
        bridge = OTELMetricsBridge(collector)

        assert bridge._base_attributes["pipeline_name"] == "test_pipeline"
        assert bridge._base_attributes["run_id"] == "run_123"

    def test_labels_passed_through(self):
        """Test labels are passed through to collector."""
        collector = MagicMock()
        collector.pipeline_name = "test"
        collector.run_id = "run_123"
        bridge = OTELMetricsBridge(collector)

        bridge.increment("test", 1, labels={"entity": "customers"})

        collector.increment.assert_called_once_with("test", 1, {"entity": "customers"})

    def test_getattr_delegates_unknown_methods(self):
        """Test unknown methods are delegated to collector."""
        collector = MagicMock()
        collector.pipeline_name = "test"
        collector.run_id = "run_123"
        collector.custom_method.return_value = "custom_result"

        bridge = OTELMetricsBridge(collector)
        result = bridge.custom_method("arg1", "arg2")

        collector.custom_method.assert_called_once_with("arg1", "arg2")
        assert result == "custom_result"


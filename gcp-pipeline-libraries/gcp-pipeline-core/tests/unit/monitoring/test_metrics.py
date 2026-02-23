"""Unit tests for MetricsCollector."""

import pytest
from unittest.mock import patch

from gcp_pipeline_core.monitoring import MetricsCollector


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_initialization(self):
        """Test initializing metrics collector."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        assert collector.pipeline_name == "test_pipeline"
        assert collector.run_id == "run-123"
        assert len(collector.counters) == 0
        assert len(collector.gauges) == 0
        assert len(collector.histograms) == 0
        assert len(collector.timers) == 0

    def test_counter_increment(self):
        """Test incrementing a counter metric."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.increment("records_processed", 100)
        collector.increment("records_processed", 50)

        assert collector.counters["records_processed"] == 150

    def test_counter_increment_default_value(self):
        """Test incrementing counter with default value."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.increment("records_processed")
        assert collector.counters["records_processed"] == 1

    def test_set_gauge(self):
        """Test setting a gauge metric."""
        collector = MetricsCollector("test", "123")
        collector.set_gauge("memory_usage", 512.5)
        assert collector.gauges["memory_usage"] == 512.5

    def test_record_histogram(self):
        """Test recording a histogram metric."""
        collector = MetricsCollector("test", "123")
        collector.record_histogram("request_latency", 0.5)
        collector.record_histogram("request_latency", 0.8)
        assert collector.histograms["request_latency"] == [0.5, 0.8]

    def test_record_timer(self):
        """Test recording a timer metric."""
        collector = MetricsCollector("test", "123")
        collector.record_timer("db_query", 1.2)
        assert collector.timers["db_query"] == [1.2]

    def test_timer_context(self):
        """Test using timer context manager."""
        collector = MetricsCollector("test", "123")
        with patch("time.time", side_effect=[10.0, 12.5]):
            with collector.start_timer() as timer:
                timer.metric_name = "custom_op"
            
        assert collector.timers["custom_op"] == [2.5]


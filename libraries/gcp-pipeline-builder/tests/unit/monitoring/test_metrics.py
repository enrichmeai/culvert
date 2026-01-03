"""Unit tests for MetricsCollector."""

import pytest

from gcp_pipeline_builder.monitoring import MetricsCollector


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


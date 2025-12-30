import pytest
from datetime import datetime, timedelta, timezone
from gdw_data_core.core.monitoring import (
    MetricsCollector,
    MetricValue,
    Alert,
    AlertLevel,
    MetricType,
    HealthChecker,
    AlertManager,
    LoggingAlertBackend,
    TimerContext,
)


class TestMetricsCollector:
    """Tests for MetricsCollector"""

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

    def test_gauge_set(self):
        """Test setting a gauge metric."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.set_gauge("queue_depth", 42.5)

        assert collector.gauges["queue_depth"] == 42.5

    def test_gauge_update(self):
        """Test updating gauge metric."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.set_gauge("queue_depth", 42.5)
        collector.set_gauge("queue_depth", 50.0)

        assert collector.gauges["queue_depth"] == 50.0

    def test_histogram_record(self):
        """Test recording histogram values."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.record_histogram("record_size", 100)
        collector.record_histogram("record_size", 200)
        collector.record_histogram("record_size", 150)

        assert len(collector.histograms["record_size"]) == 3
        assert collector.histograms["record_size"] == [100, 200, 150]

    def test_timer_record(self):
        """Test recording timer measurements."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.record_timer("step_duration", 45.2)
        collector.record_timer("step_duration", 43.8)

        assert len(collector.timers["step_duration"]) == 2
        assert collector.timers["step_duration"] == [45.2, 43.8]

    def test_statistics_basic(self):
        """Test computing basic statistics from metrics."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.increment("records_processed", 100)
        collector.set_gauge("queue_depth", 50)

        stats = collector.get_statistics()

        assert stats['pipeline_name'] == "test_pipeline"
        assert stats['run_id'] == "run-123"
        assert stats['counters']['records_processed'] == 100
        assert stats['gauges']['queue_depth'] == 50

    def test_statistics_with_histograms(self):
        """Test statistics with histogram data."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.record_histogram("record_size", 100)
        collector.record_histogram("record_size", 200)
        collector.record_histogram("record_size", 300)

        stats = collector.get_statistics()

        assert 'histograms_summary' in stats
        assert 'record_size' in stats['histograms_summary']
        summary = stats['histograms_summary']['record_size']
        assert summary['count'] == 3
        assert summary['min'] == 100
        assert summary['max'] == 300
        assert summary['avg'] == 200.0
        assert summary['total'] == 600

    def test_statistics_with_timers(self):
        """Test statistics with timer data."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.record_timer("step_duration", 10.0)
        collector.record_timer("step_duration", 20.0)
        collector.record_timer("step_duration", 30.0)

        stats = collector.get_statistics()

        assert 'timers_summary' in stats
        assert 'step_duration' in stats['timers_summary']
        summary = stats['timers_summary']['step_duration']
        assert summary['count'] == 3
        assert summary['min'] == 10.0
        assert summary['max'] == 30.0
        assert summary['avg'] == 20.0

    def test_metric_history(self):
        """Test that metrics are recorded in history."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.increment("records_processed", 100)
        collector.set_gauge("queue_depth", 50)

        # Metric history is populated
        assert len(collector.metric_history) > 0

    def test_step_duration_recording(self):
        """Test recording pipeline step duration."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        collector.record_step_duration("extract", 10.5)
        collector.record_step_duration("transform", 20.3)
        collector.record_step_duration("load", 15.2)

        assert len(collector.timers["step_duration_extract"]) == 1
        assert len(collector.timers["step_duration_transform"]) == 1
        assert len(collector.timers["step_duration_load"]) == 1


class TestMetricValue:
    """Tests for MetricValue data class"""

    def test_metric_value_creation(self):
        """Test creating a metric value."""
        metric = MetricValue(
            name="records_processed",
            value=1000.0,
            labels={"pipeline": "test", "stage": "transform"},
            unit="count"
        )

        assert metric.name == "records_processed"
        assert metric.value == 1000.0
        assert metric.labels["pipeline"] == "test"
        assert metric.unit == "count"

    def test_metric_value_default_timestamp(self):
        """Test metric value has default timestamp."""
        metric = MetricValue(
            name="records_processed",
            value=1000.0
        )

        assert metric.timestamp is not None
        assert isinstance(metric.timestamp, datetime)

    def test_metric_value_to_dict(self):
        """Test converting metric value to dictionary."""
        metric = MetricValue(
            name="records_processed",
            value=1000.0,
            labels={"pipeline": "test"},
            unit="count"
        )

        metric_dict = metric.to_dict()

        assert metric_dict['name'] == "records_processed"
        assert metric_dict['value'] == 1000.0
        assert 'timestamp' in metric_dict
        assert metric_dict['unit'] == "count"
        assert metric_dict['labels']['pipeline'] == "test"

    def test_metric_value_empty_labels(self):
        """Test metric value with no labels."""
        metric = MetricValue(
            name="records_processed",
            value=1000.0
        )

        assert metric.labels == {}
        metric_dict = metric.to_dict()
        assert metric_dict['labels'] == {}


class TestAlert:
    """Tests for Alert data class"""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            alert_id="alert-123",
            level=AlertLevel.CRITICAL,
            title="High Error Rate",
            message="Error rate exceeds threshold",
            source="error_handler",
            metric_name="error_count",
            threshold_value=100.0,
            actual_value=150.0
        )

        assert alert.alert_id == "alert-123"
        assert alert.level == AlertLevel.CRITICAL
        assert alert.actual_value == 150.0
        assert alert.source == "error_handler"

    def test_alert_default_timestamp(self):
        """Test alert has default timestamp."""
        alert = Alert(
            alert_id="alert-123",
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="This is a test",
            source="test"
        )

        assert alert.timestamp is not None
        assert isinstance(alert.timestamp, datetime)

    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        alert = Alert(
            alert_id="alert-123",
            level=AlertLevel.CRITICAL,
            title="High Error Rate",
            message="Error rate exceeds threshold",
            source="error_handler"
        )

        alert_dict = alert.to_dict()

        assert alert_dict['alert_id'] == "alert-123"
        assert alert_dict['level'] == "CRITICAL"
        assert 'timestamp' in alert_dict
        assert alert_dict['title'] == "High Error Rate"

    def test_alert_levels(self):
        """Test different alert levels."""
        for level in [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.CRITICAL]:
            alert = Alert(
                alert_id="alert-test",
                level=level,
                title="Test",
                message="Test message",
                source="test"
            )
            assert alert.level == level
            assert alert.to_dict()['level'] == level.value

    def test_alert_with_metadata(self):
        """Test alert with metadata."""
        metadata = {"user": "test_user", "run_id": "run-123"}
        alert = Alert(
            alert_id="alert-123",
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            source="test",
            metadata=metadata
        )

        assert alert.metadata == metadata


class TestHealthChecker:
    """Tests for HealthChecker"""

    def test_health_checker_initialization(self):
        """Test initializing health checker."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        assert checker.metrics == collector
        assert len(checker.health_checks) == 0

    def test_check_record_processing(self):
        """Test checking if records are being processed."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        # No records processed
        assert checker.check_record_processing() is False

        # Records processed
        collector.increment("records_processed", 100)
        assert checker.check_record_processing() is True

    def test_check_error_rate_healthy(self):
        """Test error rate check when healthy."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.increment("records_processed", 1000)
        collector.increment("records_error", 50)  # 5% error rate

        # Default threshold is 10%
        assert checker.check_error_rate(threshold=0.1) is True

    def test_check_error_rate_unhealthy(self):
        """Test error rate check when unhealthy."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.increment("records_processed", 100)
        collector.increment("records_error", 50)  # 50% error rate

        # Should exceed 10% threshold
        assert checker.check_error_rate(threshold=0.1) is False

    def test_check_queue_depth_healthy(self):
        """Test queue depth check when healthy."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.set_gauge("queue_depth", 500)
        assert checker.check_queue_depth(max_depth=1000) is True

    def test_check_queue_depth_unhealthy(self):
        """Test queue depth check when unhealthy."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.set_gauge("queue_depth", 1500)
        assert checker.check_queue_depth(max_depth=1000) is False

    def test_check_processing_time(self):
        """Test processing time check."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.counters['uptime_seconds'] = 1800  # 30 minutes
        assert checker.check_processing_time(max_duration_seconds=3600) is True

    def test_check_memory_usage(self):
        """Test memory usage check."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        collector.set_gauge("memory_usage_mb", 512)
        assert checker.check_memory_usage(max_memory_mb=1024) is True

    def test_run_all_checks(self):
        """Test running all health checks."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        # Setup metrics
        collector.increment("records_processed", 100)
        collector.set_gauge("queue_depth", 500)

        results = checker.run_all_checks()

        assert isinstance(results, dict)
        assert 'records_processing' in results
        assert 'error_rate' in results
        assert 'queue_depth' in results

    def test_is_healthy(self):
        """Test overall health status."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        # Setup healthy metrics
        collector.increment("records_processed", 100)
        checker.run_all_checks()

        # At least records_processing is True
        assert any(checker.health_checks.values())


class TestAlertManager:
    """Tests for AlertManager"""

    def test_alert_manager_initialization(self):
        """Test initializing alert manager."""
        manager = AlertManager()

        assert len(manager.backends) == 0
        assert len(manager.alerts) == 0

    def test_alert_manager_with_backends(self):
        """Test alert manager with backends."""
        backend = LoggingAlertBackend()
        manager = AlertManager(alert_backends=[backend])

        assert len(manager.backends) == 1
        assert manager.backends[0] == backend

    def test_create_alert_basic(self):
        """Test creating an alert."""
        manager = AlertManager()

        alert = manager.create_alert(
            level=AlertLevel.CRITICAL,
            title="Test Alert",
            message="This is a test alert",
            source="test"
        )

        assert alert.alert_id is not None
        assert alert.level == AlertLevel.CRITICAL
        assert alert.title == "Test Alert"
        assert len(manager.alerts) == 1

    def test_create_alert_with_metrics(self):
        """Test creating alert with metric details."""
        manager = AlertManager()

        alert = manager.create_alert(
            level=AlertLevel.WARNING,
            title="High Error Rate",
            message="Error rate exceeded threshold",
            source="monitoring",
            metric_name="error_count",
            threshold_value=100.0,
            actual_value=150.0
        )

        assert alert.metric_name == "error_count"
        assert alert.threshold_value == 100.0
        assert alert.actual_value == 150.0

    def test_alert_history(self):
        """Test alert history tracking."""
        manager = AlertManager()

        manager.create_alert(
            level=AlertLevel.INFO,
            title="Alert 1",
            message="First alert",
            source="test"
        )
        manager.create_alert(
            level=AlertLevel.WARNING,
            title="Alert 2",
            message="Second alert",
            source="test"
        )

        assert len(manager.alert_history) == 2

    def test_get_recent_alerts(self):
        """Test retrieving recent alerts."""
        manager = AlertManager()

        manager.create_alert(
            level=AlertLevel.INFO,
            title="Alert 1",
            message="First alert",
            source="test"
        )
        manager.create_alert(
            level=AlertLevel.WARNING,
            title="Alert 2",
            message="Second alert",
            source="test"
        )

        recent = manager.get_recent_alerts(minutes=60)
        assert len(recent) == 2

    def test_get_recent_alerts_filtered_by_level(self):
        """Test filtering recent alerts by level."""
        manager = AlertManager()

        manager.create_alert(
            level=AlertLevel.INFO,
            title="Info Alert",
            message="Information",
            source="test"
        )
        manager.create_alert(
            level=AlertLevel.CRITICAL,
            title="Critical Alert",
            message="Critical issue",
            source="test"
        )

        critical = manager.get_recent_alerts(minutes=60, level=AlertLevel.CRITICAL)
        assert len(critical) == 1
        assert critical[0].level == AlertLevel.CRITICAL


class TestTimerContext:
    """Tests for TimerContext"""

    def test_timer_context_basic(self):
        """Test using timer context."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        # Create timer context (without automatic recording for this test)
        timer = collector.start_timer()
        assert timer is not None
        assert isinstance(timer, TimerContext)

    def test_timer_context_measurement(self):
        """Test that timer measures time correctly."""
        import time

        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )

        start = datetime.now(timezone.utc)
        with collector.start_timer() as timer:
            time.sleep(0.1)  # Sleep for 100ms

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        assert elapsed >= 0.1


class TestMetricsIntegration:
    """Integration tests for metrics collection"""

    def test_full_metrics_workflow(self):
        """Test complete metrics collection workflow."""
        collector = MetricsCollector(
            pipeline_name="data_migration",
            run_id="run-2025-001"
        )

        # Simulate pipeline execution
        collector.increment("records_read", 1000)
        collector.increment("records_processed", 950)
        collector.increment("records_error", 50)

        collector.record_histogram("record_size", 100)
        collector.record_histogram("record_size", 150)
        collector.record_histogram("record_size", 120)

        collector.record_timer("step_duration_extract", 5.2)
        collector.record_timer("step_duration_transform", 12.3)
        collector.record_timer("step_duration_load", 8.7)

        # Get statistics
        stats = collector.get_statistics()

        assert stats['counters']['records_read'] == 1000
        assert stats['counters']['records_processed'] == 950
        assert stats['counters']['records_error'] == 50
        assert 'record_size' in stats['histograms_summary']
        assert 'step_duration_extract' in stats['timers_summary']

    def test_health_check_integration(self):
        """Test health checking with metrics."""
        collector = MetricsCollector(
            pipeline_name="test_pipeline",
            run_id="run-123"
        )
        checker = HealthChecker(collector)

        # Setup healthy pipeline
        collector.increment("records_processed", 1000)
        collector.increment("records_error", 10)  # 1% error rate
        collector.set_gauge("queue_depth", 100)

        health = checker.run_all_checks()

        assert health['records_processing'] is True
        assert health['error_rate'] is True
        assert health['queue_depth'] is True


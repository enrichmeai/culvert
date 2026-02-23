"""
Unit tests for MigrationMetrics.

Tests standardized migration metrics collection.
"""

import unittest
from gcp_pipeline_core.monitoring.metrics import MigrationMetrics


class TestMigrationMetrics(unittest.TestCase):
    """Tests for MigrationMetrics class."""

    def setUp(self):
        """Set up test metrics."""
        self.metrics = MigrationMetrics(
            run_id="application1_20260105_143022_abc123",
            systapplication1_id="Application1",
            entity_type="customers"
        )

    def test_initialization(self):
        """MigrationMetrics should initialize correctly."""
        self.assertEqual(self.metrics.run_id, "application1_20260105_143022_abc123")
        self.assertEqual(self.metrics.systapplication1_id, "Application1")
        self.assertEqual(self.metrics.entity_type, "customers")

    def test_record_read(self):
        """record_read should increment records_read counter."""
        self.metrics.record_read(100)
        self.metrics.record_read(50)

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['read'], 150)

    def test_record_parsed(self):
        """record_parsed should increment records_parsed counter."""
        self.metrics.record_parsed(90)

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['parsed'], 90)

    def test_record_validated(self):
        """record_validated should increment records_validated counter."""
        self.metrics.record_validated(80)

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['validated'], 80)

    def test_record_failed(self):
        """record_failed should increment records_failed counter."""
        self.metrics.record_failed(10)
        self.metrics.record_failed(5, error_type="MISSING_FIELD")

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['failed'], 15)

    def test_record_written(self):
        """record_written should increment records_written counter."""
        self.metrics.record_written(75)

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['written'], 75)

    def test_record_skipped(self):
        """record_skipped should increment records_skipped counter."""
        self.metrics.record_skipped(5, reason="duplicate")

        summary = self.metrics.get_summary()
        self.assertEqual(summary['counts']['skipped'], 5)

    def test_validation_success_rate(self):
        """Should calculate validation success rate correctly."""
        self.metrics.record_read(100)
        self.metrics.record_validated(90)
        self.metrics.record_failed(10)

        summary = self.metrics.get_summary()
        self.assertEqual(summary['rates']['validation_success_rate'], 90.0)
        self.assertEqual(summary['rates']['validation_failure_rate'], 10.0)

    def test_validation_rate_zero_reads(self):
        """Should handle zero reads without division error."""
        summary = self.metrics.get_summary()
        self.assertEqual(summary['rates']['validation_success_rate'], 0)
        self.assertEqual(summary['rates']['validation_failure_rate'], 0)

    def test_get_summary_includes_context(self):
        """get_summary should include run_id, systapplication1_id, entity_type."""
        summary = self.metrics.get_summary()

        self.assertEqual(summary['run_id'], "application1_20260105_143022_abc123")
        self.assertEqual(summary['systapplication1_id'], "Application1")
        self.assertEqual(summary['entity_type'], "customers")

    def test_to_job_record(self):
        """to_job_record should return job control record format."""
        self.metrics.record_read(100)
        self.metrics.record_validated(95)
        self.metrics.record_failed(5)
        self.metrics.record_written(95)

        record = self.metrics.to_job_record()

        self.assertEqual(record['run_id'], "application1_20260105_143022_abc123")
        self.assertEqual(record['systapplication1_id'], "Application1")
        self.assertEqual(record['entity_type'], "customers")
        self.assertEqual(record['records_read'], 100)
        self.assertEqual(record['records_validated'], 95)
        self.assertEqual(record['records_failed'], 5)
        self.assertEqual(record['records_written'], 95)
        self.assertEqual(record['validation_success_rate'], 95.0)

    def test_record_validation_error_by_type(self):
        """record_validation_error should track errors by type."""
        self.metrics.record_validation_error("MISSING_SSN", 5)
        self.metrics.record_validation_error("INVALID_STATUS", 3)

        # Should increment validation_errors counter
        stats = self.metrics._collector.get_statistics()
        self.assertEqual(stats['counters']['validation_errors'], 8)

    def test_record_processing_time(self):
        """record_processing_time should record duration histogram."""
        self.metrics.record_processing_time(150.5)
        self.metrics.record_processing_time(200.0)

        stats = self.metrics._collector.get_statistics()
        self.assertIn('processing_duration_ms', stats['histograms_summary'])
        self.assertEqual(stats['histograms_summary']['processing_duration_ms']['count'], 2)

    def test_start_timer(self):
        """start_timer should return TimerContext."""
        timer = self.metrics.start_timer("validation")
        self.assertIsNotNone(timer)


class TestMigrationMetricsWithoutEntityType(unittest.TestCase):
    """Test MigrationMetrics without entity_type."""

    def test_initialization_without_entity_type(self):
        """Should work without entity_type."""
        metrics = MigrationMetrics(
            run_id="run_123",
            systapplication1_id="Application1"
        )
        self.assertIsNone(metrics.entity_type)

        summary = metrics.get_summary()
        self.assertIsNone(summary['entity_type'])


class TestMigrationMetricsLabels(unittest.TestCase):
    """Test that labels are correctly applied."""

    def test_labels_include_context(self):
        """All metrics should include run_id, systapplication1_id labels."""
        metrics = MigrationMetrics(
            run_id="run_123",
            systapplication1_id="Application1",
            entity_type="accounts"
        )

        # Internal method check
        labels = metrics._get_labels()

        self.assertEqual(labels['run_id'], "run_123")
        self.assertEqual(labels['systapplication1_id'], "Application1")
        self.assertEqual(labels['entity_type'], "accounts")

    def test_extra_labels_merged(self):
        """Extra labels should be merged with standard labels."""
        metrics = MigrationMetrics(
            run_id="run_123",
            systapplication1_id="Application1"
        )

        labels = metrics._get_labels({'custom': 'value'})

        self.assertEqual(labels['run_id'], "run_123")
        self.assertEqual(labels['custom'], 'value')


if __name__ == '__main__':
    unittest.main()


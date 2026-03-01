from unittest.mock import MagicMock, patch
from gcp_pipeline_core.monitoring.metrics import MigrationMetrics

def test_migration_metrics_finops_integration():
    with patch('gcp_pipeline_core.monitoring.metrics.MetricsCollector') as MockCollector:
        mock_collector_instance = MockCollector.return_value
        metrics = MigrationMetrics(
            run_id="test-run",
            system_id="test-system"
        )
        
        metrics.record_cost(1.25)
        metrics.record_bytes_scanned(1000000)
        metrics.record_bytes_written(500000)
        
        # Check if collector was called with correct FinOps metric names
        mock_collector_instance.set_gauge.assert_any_call(
            MigrationMetrics.ESTIMATED_COST_USD, 
            1.25, 
            metrics._get_labels()
        )
        mock_collector_instance.increment.assert_any_call(
            MigrationMetrics.BILLED_BYTES_SCANNED, 
            1000000, 
            metrics._get_labels()
        )
        mock_collector_instance.increment.assert_any_call(
            MigrationMetrics.BILLED_BYTES_WRITTEN, 
            500000, 
            metrics._get_labels()
        )

def test_migration_metrics_to_job_record_finops():
    with patch('gcp_pipeline_core.monitoring.metrics.MetricsCollector') as MockCollector:
        mock_collector_instance = MockCollector.return_value
        # Mock return value for get_statistics
        mock_collector_instance.get_statistics.return_value = {
            'counters': {
                MigrationMetrics.RECORDS_READ: 100,
                MigrationMetrics.RECORDS_VALIDATED: 90,
                MigrationMetrics.RECORDS_FAILED: 10,
                MigrationMetrics.RECORDS_WRITTEN: 80,
                MigrationMetrics.BILLED_BYTES_SCANNED: 2000,
                MigrationMetrics.BILLED_BYTES_WRITTEN: 1000,
            },
            'gauges': {
                MigrationMetrics.ESTIMATED_COST_USD: 0.50,
            },
            'histograms': {},
            'uptime_seconds': 10,
            'start_time': None
        }
        
        metrics = MigrationMetrics(
            run_id="test-run",
            system_id="test-system"
        )
        
        record = metrics.to_job_record()
        
        assert record['estimated_cost_usd'] == 0.50
        assert record['billed_bytes_scanned'] == 2000
        assert record['billed_bytes_written'] == 1000

def test_migration_metrics_new_finops_integration():
    with patch('gcp_pipeline_core.monitoring.metrics.MetricsCollector') as MockCollector:
        mock_collector_instance = MockCollector.return_value
        metrics = MigrationMetrics(
            run_id="test-run",
            system_id="test-system"
        )
        
        metrics.record_bytes_stored(3000)
        metrics.record_messages_count(5)
        
        mock_collector_instance.increment.assert_any_call(
            MigrationMetrics.BILLED_BYTES_STORED, 
            3000, 
            metrics._get_labels()
        )
        mock_collector_instance.increment.assert_any_call(
            MigrationMetrics.BILLED_MESSAGES_COUNT, 
            5, 
            metrics._get_labels()
        )

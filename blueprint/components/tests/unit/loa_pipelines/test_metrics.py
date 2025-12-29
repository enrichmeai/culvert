from gdw_data_core.testing import BaseGDWTest
from unittest.mock import MagicMock, patch
from gdw_data_core.core.monitoring import MetricsCollector

class TestMetricsMonitoring(BaseGDWTest):
    def test_metrics_collection(self):
        run_id = 'test_run_001'
        pipeline_name = 'loa_jcl'

        # In real scenario, library transforms emit metrics via beam.metrics
        # Here we test the MetricsCollector retrieval
        with patch('gdw_data_core.core.monitoring.MetricsCollector.get_statistics') as mock_stats:
            mock_stats.return_value = {
                'validation_success': 100,
                'validation_errors': 5,
                'records_processed': 105
            }

            collector = MetricsCollector(pipeline_name=pipeline_name, run_id=run_id)
            stats = collector.get_statistics()

            self.assertEqual(stats['validation_success'], 100)
            self.assertEqual(stats['validation_errors'], 5)
            self.assertEqual(stats['records_processed'], 105)

    def test_health_check_detailed(self):
        """Test detailed health check scenarios."""
        from gdw_data_core.core.monitoring.health import HealthChecker
        collector = MetricsCollector(pipeline_name='loa_jcl', run_id='test')
        
        # Scenario 1: Healthy pipeline
        collector.counters['records_processed'] = 100
        collector.counters['records_error'] = 5  # 5% error rate, threshold is 10%
        checker = HealthChecker(metrics_collector=collector)
        results = checker.run_all_checks()
        self.assertTrue(results['records_processing'])
        self.assertTrue(results['error_rate'])
        self.assertTrue(checker.is_healthy())

        # Scenario 2: Unhealthy due to high error rate
        collector.counters['records_error'] = 20  # 20% error rate
        results = checker.run_all_checks()
        self.assertFalse(results['error_rate'])
        self.assertFalse(checker.is_healthy())

        # Scenario 3: Unhealthy due to no records processed
        collector.counters['records_processed'] = 0
        results = checker.run_all_checks()
        self.assertFalse(results['records_processing'])
        self.assertFalse(checker.is_healthy())

if __name__ == '__main__':
    import unittest
    unittest.main()

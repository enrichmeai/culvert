"""
Unit tests for ReconciliationEngine.

Tests automated reconciliation between source file counts and BigQuery counts.
"""

import unittest
from unittest.mock import MagicMock, patch

from gcp_pipeline_builder.audit.reconciliation import (
    ReconciliationEngine,
    ReconciliationResult,
    ReconciliationStatus,
)


class TestReconciliationEngine(unittest.TestCase):
    """Tests for ReconciliationEngine class."""

    def setUp(self):
        """Set up test engine."""
        self.engine = ReconciliationEngine(
            entity_type="customers",
            run_id="em_20260105_143022_abc123",
            project_id="test-project"
        )

    def test_initialization(self):
        """ReconciliationEngine should initialize correctly."""
        self.assertEqual(self.engine.entity_type, "customers")
        self.assertEqual(self.engine.run_id, "em_20260105_143022_abc123")
        self.assertEqual(self.engine.project_id, "test-project")

    def test_reconcile_counts_match(self):
        """Should return RECONCILED when counts match."""
        result = self.engine.reconcile_counts(
            source_count=1000,
            destination_count=1000,
            error_count=0
        )

        self.assertIsInstance(result, ReconciliationResult)
        self.assertEqual(result.status, ReconciliationStatus.RECONCILED)
        self.assertTrue(result.is_reconciled)
        self.assertEqual(result.difference, 0)
        self.assertEqual(result.match_percentage, 100.0)

    def test_reconcile_counts_with_errors(self):
        """Should return RECONCILED when source = destination + errors."""
        result = self.engine.reconcile_counts(
            source_count=1000,
            destination_count=950,
            error_count=50
        )

        self.assertEqual(result.status, ReconciliationStatus.RECONCILED)
        self.assertTrue(result.is_reconciled)
        self.assertEqual(result.difference, 0)
        self.assertEqual(result.actual_count, 950)
        self.assertEqual(result.error_count, 50)

    def test_reconcile_counts_mismatch(self):
        """Should return MISMATCH when counts don't match."""
        result = self.engine.reconcile_counts(
            source_count=1000,
            destination_count=900,
            error_count=0
        )

        self.assertEqual(result.status, ReconciliationStatus.MISMATCH)
        self.assertFalse(result.is_reconciled)
        self.assertEqual(result.difference, 100)
        self.assertEqual(result.expected_count, 1000)
        self.assertEqual(result.actual_count, 900)

    def test_reconcile_counts_extra_records(self):
        """Should handle case where destination has more than source."""
        result = self.engine.reconcile_counts(
            source_count=1000,
            destination_count=1100,
            error_count=0
        )

        self.assertEqual(result.status, ReconciliationStatus.MISMATCH)
        self.assertEqual(result.difference, -100)
        self.assertIn("Extra", result.message)

    def test_reconcile_counts_zero_source(self):
        """Should handle zero source count."""
        result = self.engine.reconcile_counts(
            source_count=0,
            destination_count=0,
            error_count=0
        )

        self.assertEqual(result.status, ReconciliationStatus.RECONCILED)
        self.assertEqual(result.match_percentage, 0)

    def test_result_to_dict(self):
        """ReconciliationResult.to_dict should return correct format."""
        result = self.engine.reconcile_counts(
            source_count=1000,
            destination_count=1000
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict['entity_type'], 'customers')
        self.assertEqual(result_dict['run_id'], 'em_20260105_143022_abc123')
        self.assertEqual(result_dict['expected_count'], 1000)
        self.assertEqual(result_dict['actual_count'], 1000)
        self.assertEqual(result_dict['status'], 'RECONCILED')

    def test_get_result(self):
        """get_result should return last result."""
        self.engine.reconcile_counts(source_count=100, destination_count=100)

        result = self.engine.get_result()

        self.assertIsNotNone(result)
        self.assertEqual(result.expected_count, 100)

    def test_get_reconciliation_report(self):
        """get_reconciliation_report should return formatted string."""
        self.engine.reconcile_counts(source_count=1000, destination_count=950, error_count=50)

        report = self.engine.get_reconciliation_report()

        self.assertIn("CUSTOMERS", report)
        self.assertIn("1,000", report)
        self.assertIn("RECONCILED", report)

    def test_get_reconciliation_report_no_data(self):
        """get_reconciliation_report should handle no data."""
        report = self.engine.get_reconciliation_report()

        self.assertEqual(report, "No reconciliation data available")


class TestReconciliationWithBigQuery(unittest.TestCase):
    """Tests for BigQuery integration."""

    def setUp(self):
        """Set up test engine."""
        self.engine = ReconciliationEngine(
            entity_type="customers",
            run_id="em_20260105_143022_abc123",
            project_id="test-project"
        )

    @patch('gcp_pipeline_builder.audit.reconciliation.ReconciliationEngine._query_count')
    def test_reconcile_with_bigquery_match(self, mock_query):
        """Should reconcile with BigQuery counts."""
        mock_query.return_value = 1000
        mock_client = MagicMock()

        result = self.engine.reconcile_with_bigquery(
            expected_count=1000,
            destination_table="project.dataset.table",
            bq_client=mock_client
        )

        self.assertEqual(result.status, ReconciliationStatus.RECONCILED)
        self.assertEqual(result.actual_count, 1000)

    @patch('gcp_pipeline_builder.audit.reconciliation.ReconciliationEngine._query_count')
    def test_reconcile_with_bigquery_mismatch(self, mock_query):
        """Should detect mismatch with BigQuery."""
        mock_query.return_value = 900
        mock_client = MagicMock()

        result = self.engine.reconcile_with_bigquery(
            expected_count=1000,
            destination_table="project.dataset.table",
            bq_client=mock_client
        )

        self.assertEqual(result.status, ReconciliationStatus.MISMATCH)
        self.assertEqual(result.difference, 100)

    @patch('gcp_pipeline_builder.audit.reconciliation.ReconciliationEngine._query_count')
    def test_reconcile_with_error_table(self, mock_query):
        """Should include error table count."""
        # First call for destination, second for error table
        mock_query.side_effect = [950, 50]
        mock_client = MagicMock()

        result = self.engine.reconcile_with_bigquery(
            expected_count=1000,
            destination_table="project.dataset.table",
            error_table="project.dataset.table_errors",
            bq_client=mock_client
        )

        self.assertEqual(result.status, ReconciliationStatus.RECONCILED)
        self.assertEqual(result.actual_count, 950)
        self.assertEqual(result.error_count, 50)

    def test_reconcile_with_bigquery_error(self):
        """Should handle BigQuery errors gracefully."""
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("BigQuery error")

        result = self.engine.reconcile_with_bigquery(
            expected_count=1000,
            destination_table="project.dataset.table",
            bq_client=mock_client
        )

        self.assertEqual(result.status, ReconciliationStatus.ERROR)
        self.assertIn("error", result.message.lower())


class TestReconciliationFromTrailer(unittest.TestCase):
    """Tests for trailer record integration."""

    def setUp(self):
        """Set up test engine."""
        self.engine = ReconciliationEngine(
            entity_type="customers",
            run_id="em_20260105_143022_abc123"
        )

    @patch('gcp_pipeline_builder.audit.reconciliation.ReconciliationEngine.reconcile_with_bigquery')
    def test_reconcile_from_trailer(self, mock_reconcile):
        """Should extract count from trailer record."""
        mock_trailer = MagicMock()
        mock_trailer.record_count = 1000

        mock_reconcile.return_value = ReconciliationResult(
            entity_type="customers",
            run_id="test",
            expected_count=1000,
            actual_count=1000,
            error_count=0,
            status=ReconciliationStatus.RECONCILED,
            difference=0,
            match_percentage=100.0
        )

        result = self.engine.reconcile_from_trailer(
            trailer_record=mock_trailer,
            destination_table="project.dataset.table"
        )

        mock_reconcile.assert_called_once_with(
            expected_count=1000,
            destination_table="project.dataset.table",
            error_table=None,
            bq_client=None
        )


class TestReconciliationWithLogger(unittest.TestCase):
    """Tests for structured logging integration."""

    def test_logs_success_with_logger(self):
        """Should use structured logger for success."""
        mock_logger = MagicMock()
        engine = ReconciliationEngine(
            entity_type="customers",
            run_id="test",
            logger=mock_logger
        )

        engine.reconcile_counts(source_count=1000, destination_count=1000)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        self.assertIn("passed", call_args[0][0].lower())

    def test_logs_failure_with_logger(self):
        """Should use structured logger for failure."""
        mock_logger = MagicMock()
        engine = ReconciliationEngine(
            entity_type="customers",
            run_id="test",
            logger=mock_logger
        )

        engine.reconcile_counts(source_count=1000, destination_count=900)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        self.assertIn("failed", call_args[0][0].lower())


if __name__ == '__main__':
    unittest.main()


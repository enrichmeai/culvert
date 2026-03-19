"""Unit tests for update_cost_metrics in JobControlRepository."""

import unittest
from unittest.mock import MagicMock, patch

from gcp_pipeline_core.job_control import JobControlRepository


class TestUpdateCostMetrics(unittest.TestCase):
    """Test the update_cost_metrics method."""

    @patch('gcp_pipeline_core.job_control.repository.bigquery.Client')
    def setUp(self, mock_bq_client):
        self.mock_client = MagicMock()
        mock_bq_client.return_value = self.mock_client
        self.repo = JobControlRepository(project_id="test-project")

    def test_update_cost_metrics_sends_query(self):
        """Test that update_cost_metrics issues an UPDATE query."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.update_cost_metrics(
            run_id="run_001",
            estimated_cost_usd=0.0042,
            billed_bytes_scanned=4_500_000,
            billed_bytes_written=1_200_000,
        )

        self.mock_client.query.assert_called_once()
        query = self.mock_client.query.call_args[0][0]
        self.assertIn("UPDATE", query)
        self.assertIn("estimated_cost_usd", query)
        self.assertIn("billed_bytes_scanned", query)
        self.assertIn("billed_bytes_written", query)

    def test_update_cost_metrics_with_zero_values(self):
        """Test with zero cost values (e.g., load jobs are free)."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.update_cost_metrics(
            run_id="run_002",
            estimated_cost_usd=0.0,
            billed_bytes_scanned=0,
            billed_bytes_written=0,
        )

        self.mock_client.query.assert_called_once()

    def test_update_cost_metrics_default_values(self):
        """Test with defaults (all zeroes)."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.update_cost_metrics(run_id="run_003")

        self.mock_client.query.assert_called_once()


if __name__ == '__main__':
    unittest.main()

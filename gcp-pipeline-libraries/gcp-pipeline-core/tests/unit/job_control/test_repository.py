"""Unit tests for JobControlRepository with mocking."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from gcp_pipeline_core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)


class TestJobControlRepository(unittest.TestCase):
    """Test JobControlRepository class with mocked BigQuery."""

    @patch('gcp_pipeline_core.job_control.repository.bigquery.Client')
    def setUp(self, mock_bq_client):
        """Set up repository with mocked BigQuery client."""
        self.mock_client = MagicMock()
        mock_bq_client.return_value = self.mock_client
        self.repo = JobControlRepository(project_id="test-project")

    def test_init(self):
        """Test repository initialization."""
        self.assertEqual(self.repo.project_id, "test-project")
        self.assertEqual(self.repo.dataset, "job_control")
        self.assertEqual(self.repo.table, "pipeline_jobs")
        self.assertEqual(
            self.repo.full_table_id,
            "test-project.job_control.pipeline_jobs"
        )

    def test_init_custom_dataset_table(self):
        """Test repository with custom dataset and table."""
        with patch('gcp_pipeline_core.job_control.repository.bigquery.Client'):
            repo = JobControlRepository(
                project_id="test-project",
                dataset="custom_dataset",
                table="custom_table"
            )

        self.assertEqual(
            repo.full_table_id,
            "test-project.custom_dataset.custom_table"
        )

    def test_create_job(self):
        """Test creating a job record."""
        job = PipelineJob(
            run_id="application1_customer_20260101_001",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
            source_files=["gs://bucket/file.csv"],
        )

        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.create_job(job)

        self.mock_client.query.assert_called_once()
        call_args = self.mock_client.query.call_args
        query = call_args[0][0]

        self.assertIn("INSERT INTO", query)
        self.assertIn("run_id", query)
        self.assertIn("system_id", query)

    def test_update_status_running(self):
        """Test updating job status to RUNNING."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.update_status("test_run_001", JobStatus.RUNNING)

        self.mock_client.query.assert_called_once()
        call_args = self.mock_client.query.call_args
        query = call_args[0][0]

        self.assertIn("UPDATE", query)
        self.assertIn("started_at = CURRENT_TIMESTAMP()", query)

    def test_update_status_success(self):
        """Test updating job status to SUCCESS with record count."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.update_status(
            "test_run_001",
            JobStatus.SUCCESS,
            total_records=5000
        )

        self.mock_client.query.assert_called_once()
        call_args = self.mock_client.query.call_args
        query = call_args[0][0]

        self.assertIn("UPDATE", query)
        self.assertIn("completed_at = CURRENT_TIMESTAMP()", query)
        self.assertIn("total_records", query)

    def test_mark_failed(self):
        """Test marking a job as failed."""
        mock_query_job = MagicMock()
        self.mock_client.query.return_value = mock_query_job

        self.repo.mark_failed(
            run_id="test_run_001",
            error_code="E001",
            error_message="File validation failed",
            failure_stage=FailureStage.FILE_VALIDATION,
            error_file_path="gs://bucket/errors/error.json"
        )

        self.mock_client.query.assert_called_once()
        call_args = self.mock_client.query.call_args
        query = call_args[0][0]

        self.assertIn("UPDATE", query)
        self.assertIn("status = 'FAILED'", query)
        self.assertIn("error_code", query)
        self.assertIn("failure_stage", query)
        self.assertIn("failed_at = CURRENT_TIMESTAMP()", query)

    def test_get_job_found(self):
        """Test getting an existing job."""
        mock_row = MagicMock()
        mock_row.run_id = "test_run_001"
        mock_row.system_id = "Application1"
        mock_row.entity_type = "Customer"
        mock_row.extract_date = date(2026, 1, 1)
        mock_row.status = "SUCCESS"
        mock_row.started_at = None
        mock_row.completed_at = None
        mock_row.total_records = 5000
        mock_row.error_code = None
        mock_row.error_message = None

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [mock_row]
        self.mock_client.query.return_value = mock_query_job

        job = self.repo.get_job("test_run_001")

        self.assertIsNotNone(job)
        self.assertEqual(job.run_id, "test_run_001")
        self.assertEqual(job.system_id, "Application1")
        self.assertEqual(job.status, JobStatus.SUCCESS)
        self.assertEqual(job.total_records, 5000)

    def test_get_job_not_found(self):
        """Test getting a non-existent job."""
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = []
        self.mock_client.query.return_value = mock_query_job

        job = self.repo.get_job("nonexistent")

        self.assertIsNone(job)

    def test_get_entity_status(self):
        """Test getting entity status for a system/date."""
        mock_row1 = MagicMock()
        mock_row1.entity_type = "customers"
        mock_row1.status = "SUCCESS"
        mock_row1.run_id = "run_001"

        mock_row2 = MagicMock()
        mock_row2.entity_type = "accounts"
        mock_row2.status = "RUNNING"
        mock_row2.run_id = "run_002"

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [mock_row1, mock_row2]
        self.mock_client.query.return_value = mock_query_job

        statuses = self.repo.get_entity_status("Application1", date(2026, 1, 1))

        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0]["entity_type"], "customers")
        self.assertEqual(statuses[0]["status"], "SUCCESS")
        self.assertEqual(statuses[1]["entity_type"], "accounts")
        self.assertEqual(statuses[1]["status"], "RUNNING")


if __name__ == '__main__':
    unittest.main()


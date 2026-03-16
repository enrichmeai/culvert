"""Unit tests for job control models (dataclasses)."""

import unittest
from datetime import date, datetime, timezone

from gcp_pipeline_core.job_control import (
    JobStatus,
    FailureStage,
    PipelineJob,
)


class TestPipelineJob(unittest.TestCase):
    """Test PipelineJob dataclass."""

    def test_create_minimal_job(self):
        """Test creating a job with minimal required fields."""
        job = PipelineJob(
            run_id="application1_customer_20260101_001",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertEqual(job.run_id, "application1_customer_20260101_001")
        self.assertEqual(job.system_id, "Application1")
        self.assertEqual(job.entity_type, "Customer")
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertEqual(job.source_files, [])

    def test_create_job_with_all_fields(self):
        """Test creating a job with all fields."""
        now = datetime.now(tz=timezone.utc)
        job = PipelineJob(
            run_id="application1_customer_20260101_001",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
            status=JobStatus.RUNNING,
            started_at=now,
            source_files=["gs://bucket/file1.csv", "gs://bucket/file2.csv"],
            total_records=5000,
        )

        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertEqual(job.started_at, now)
        self.assertEqual(len(job.source_files), 2)
        self.assertEqual(job.total_records, 5000)

    def test_job_with_error_info(self):
        """Test creating a failed job with error info."""
        job = PipelineJob(
            run_id="application1_customer_20260101_001",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
            status=JobStatus.FAILED,
            error_code="E001",
            error_message="File validation failed",
            failure_stage=FailureStage.FILE_VALIDATION,
            error_file_path="gs://bucket/errors/file.json",
        )

        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.error_code, "E001")
        self.assertEqual(job.failure_stage, FailureStage.FILE_VALIDATION)

    def test_job_created_at_default(self):
        """Test that created_at is auto-populated."""
        before = datetime.now(tz=timezone.utc)
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        after = datetime.now(tz=timezone.utc)

        self.assertIsNotNone(job.created_at)
        self.assertGreaterEqual(job.created_at, before)
        self.assertLessEqual(job.created_at, after)

    def test_job_source_files_default_empty(self):
        """Test source_files defaults to empty list."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertEqual(job.source_files, [])
        # Verify it's a new list instance
        job.source_files.append("gs://bucket/file.csv")

        job2 = PipelineJob(
            run_id="test2",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertEqual(job2.source_files, [])

    def test_job_type_default_none(self):
        """Test job_type defaults to None for backward compatibility."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertIsNone(job.job_type)

    def test_job_type_set_to_odp(self):
        """Test job_type can be set to ODP_INGESTION."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
            job_type="ODP_INGESTION",
        )
        self.assertEqual(job.job_type, "ODP_INGESTION")

    def test_retry_count_defaults(self):
        """Test retry_count and max_retries defaults."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertEqual(job.retry_count, 0)
        self.assertEqual(job.max_retries, 3)

    def test_retry_count_custom(self):
        """Test custom retry_count and max_retries."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
            retry_count=2,
            max_retries=5,
        )
        self.assertEqual(job.retry_count, 2)
        self.assertEqual(job.max_retries, 5)

    def test_parent_run_ids_default_empty(self):
        """Test parent_run_ids defaults to empty list."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertEqual(job.parent_run_ids, [])

    def test_fdp_job_with_lineage(self):
        """Test FDP job with parent_run_ids and dbt_model_name."""
        job = PipelineJob(
            run_id="transform_event_transaction_excess_20260101",
            system_id="GENERIC",
            entity_type="event_transaction_excess",
            extract_date=date(2026, 1, 1),
            job_type="FDP_TRANSFORMATION",
            dbt_model_name="event_transaction_excess",
            parent_run_ids=["generic_customers_20260101", "generic_accounts_20260101"],
        )
        self.assertEqual(job.job_type, "FDP_TRANSFORMATION")
        self.assertEqual(job.dbt_model_name, "event_transaction_excess")
        self.assertEqual(len(job.parent_run_ids), 2)
        self.assertIn("generic_customers_20260101", job.parent_run_ids)

    def test_dbt_model_name_default_none(self):
        """Test dbt_model_name defaults to None."""
        job = PipelineJob(
            run_id="test",
            system_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertIsNone(job.dbt_model_name)


if __name__ == '__main__':
    unittest.main()


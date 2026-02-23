"""Unit tests for job control models (dataclasses)."""

import unittest
from datetime import date, datetime

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
            systapplication1_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertEqual(job.run_id, "application1_customer_20260101_001")
        self.assertEqual(job.systapplication1_id, "Application1")
        self.assertEqual(job.entity_type, "Customer")
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertEqual(job.source_files, [])

    def test_create_job_with_all_fields(self):
        """Test creating a job with all fields."""
        now = datetime.utcnow()
        job = PipelineJob(
            run_id="application1_customer_20260101_001",
            systapplication1_id="Application1",
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
            systapplication1_id="Application1",
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
        before = datetime.utcnow()
        job = PipelineJob(
            run_id="test",
            systapplication1_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        after = datetime.utcnow()

        self.assertIsNotNone(job.created_at)
        self.assertGreaterEqual(job.created_at, before)
        self.assertLessEqual(job.created_at, after)

    def test_job_source_files_default_empty(self):
        """Test source_files defaults to empty list."""
        job = PipelineJob(
            run_id="test",
            systapplication1_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertEqual(job.source_files, [])
        # Verify it's a new list instance
        job.source_files.append("gs://bucket/file.csv")

        job2 = PipelineJob(
            run_id="test2",
            systapplication1_id="Application1",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )
        self.assertEqual(job2.source_files, [])


if __name__ == '__main__':
    unittest.main()


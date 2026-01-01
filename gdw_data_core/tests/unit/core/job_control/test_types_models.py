"""Unit tests for job control types and models."""

import unittest
from datetime import date, datetime

from gdw_data_core.core.job_control import (
    JobStatus,
    FailureStage,
    PipelineJob,
)


class TestJobStatus(unittest.TestCase):
    """Test JobStatus enum."""

    def test_job_status_values(self):
        """Test all job status values exist."""
        self.assertEqual(JobStatus.PENDING.value, "PENDING")
        self.assertEqual(JobStatus.RUNNING.value, "RUNNING")
        self.assertEqual(JobStatus.SUCCESS.value, "SUCCESS")
        self.assertEqual(JobStatus.FAILED.value, "FAILED")
        self.assertEqual(JobStatus.RETRYING.value, "RETRYING")
        self.assertEqual(JobStatus.QUARANTINED.value, "QUARANTINED")

    def test_job_status_from_string(self):
        """Test creating JobStatus from string value."""
        status = JobStatus("SUCCESS")
        self.assertEqual(status, JobStatus.SUCCESS)


class TestFailureStage(unittest.TestCase):
    """Test FailureStage enum."""

    def test_failure_stage_values(self):
        """Test all failure stage values exist."""
        self.assertEqual(FailureStage.FILE_DISCOVERY.value, "FILE_DISCOVERY")
        self.assertEqual(FailureStage.FILE_VALIDATION.value, "FILE_VALIDATION")
        self.assertEqual(FailureStage.DATA_QUALITY.value, "DATA_QUALITY")
        self.assertEqual(FailureStage.ODP_LOAD.value, "ODP_LOAD")
        self.assertEqual(FailureStage.TRANSFORMATION.value, "TRANSFORMATION")


class TestPipelineJob(unittest.TestCase):
    """Test PipelineJob dataclass."""

    def test_create_minimal_job(self):
        """Test creating a job with minimal required fields."""
        job = PipelineJob(
            run_id="em_customer_20260101_001",
            system_id="EM",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertEqual(job.run_id, "em_customer_20260101_001")
        self.assertEqual(job.system_id, "EM")
        self.assertEqual(job.entity_type, "Customer")
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertEqual(job.source_files, [])

    def test_create_job_with_all_fields(self):
        """Test creating a job with all fields."""
        now = datetime.utcnow()
        job = PipelineJob(
            run_id="em_customer_20260101_001",
            system_id="EM",
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
            run_id="em_customer_20260101_001",
            system_id="EM",
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
        job = PipelineJob(
            run_id="test_001",
            system_id="EM",
            entity_type="Customer",
            extract_date=date(2026, 1, 1),
        )

        self.assertIsNotNone(job.created_at)
        self.assertIsInstance(job.created_at, datetime)


if __name__ == '__main__':
    unittest.main()


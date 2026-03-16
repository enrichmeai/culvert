"""Unit tests for job control types (enums)."""

import unittest

from gcp_pipeline_core.job_control import (
    JobStatus,
    FailureStage,
    JobType,
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

    def test_all_statuses_defined(self):
        """Test that all expected statuses are defined."""
        statuses = [s.value for s in JobStatus]
        self.assertIn("PENDING", statuses)
        self.assertIn("RUNNING", statuses)
        self.assertIn("SUCCESS", statuses)
        self.assertIn("FAILED", statuses)


class TestFailureStage(unittest.TestCase):
    """Test FailureStage enum."""

    def test_failure_stage_values(self):
        """Test all failure stage values exist."""
        self.assertEqual(FailureStage.FILE_DISCOVERY.value, "FILE_DISCOVERY")
        self.assertEqual(FailureStage.FILE_VALIDATION.value, "FILE_VALIDATION")
        self.assertEqual(FailureStage.DATA_QUALITY.value, "DATA_QUALITY")
        self.assertEqual(FailureStage.ODP_LOAD.value, "ODP_LOAD")
        self.assertEqual(FailureStage.TRANSFORMATION.value, "TRANSFORMATION")

    def test_all_stages_defined(self):
        """Test that all expected stages are defined."""
        stages = [s.value for s in FailureStage]
        self.assertIn("FILE_DISCOVERY", stages)
        self.assertIn("FILE_VALIDATION", stages)
        self.assertIn("DATA_QUALITY", stages)
        self.assertIn("ODP_LOAD", stages)
        self.assertIn("TRANSFORMATION", stages)
        self.assertIn("RECONCILIATION", stages)

    def test_reconciliation_stage(self):
        """Test RECONCILIATION failure stage exists."""
        self.assertEqual(FailureStage.RECONCILIATION.value, "RECONCILIATION")
        stage = FailureStage("RECONCILIATION")
        self.assertEqual(stage, FailureStage.RECONCILIATION)


class TestJobType(unittest.TestCase):
    """Test JobType enum."""

    def test_job_type_values(self):
        """Test all job type values exist."""
        self.assertEqual(JobType.ODP_INGESTION.value, "ODP_INGESTION")
        self.assertEqual(JobType.FDP_TRANSFORMATION.value, "FDP_TRANSFORMATION")
        self.assertEqual(JobType.CDP_TRANSFORMATION.value, "CDP_TRANSFORMATION")

    def test_job_type_from_string(self):
        """Test creating JobType from string value."""
        jt = JobType("ODP_INGESTION")
        self.assertEqual(jt, JobType.ODP_INGESTION)

    def test_all_job_types_defined(self):
        """Test that all expected job types are defined."""
        types = [t.value for t in JobType]
        self.assertIn("ODP_INGESTION", types)
        self.assertIn("FDP_TRANSFORMATION", types)
        self.assertIn("CDP_TRANSFORMATION", types)


if __name__ == '__main__':
    unittest.main()


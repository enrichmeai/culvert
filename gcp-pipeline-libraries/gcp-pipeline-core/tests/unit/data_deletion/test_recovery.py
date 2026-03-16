"""Tests for recovery management — in-memory and GCS-backed."""

import json
import unittest
from unittest.mock import MagicMock, patch

from gcp_pipeline_core.data_deletion.recovery import (
    RecoveryManager,
    RecoveryPoint,
    GCSRecoveryManager,
)


class TestRecoveryManager(unittest.TestCase):
    """Test in-memory RecoveryManager."""

    def setUp(self):
        self.manager = RecoveryManager()

    def test_create_recovery_point(self):
        """Test creating a recovery point with state."""
        rp = self.manager.create_recovery_point(
            "after_validation",
            {"records_valid": 500, "records_error": 3},
        )
        self.assertEqual(rp.checkpoint_name, "after_validation")
        self.assertEqual(rp.state["records_valid"], 500)
        self.assertIsNotNone(rp.timestamp)

    def test_restore_recovery_point(self):
        """Test restoring from a recovery point."""
        self.manager.create_recovery_point("cp1", {"step": "load"})
        result = self.manager.restore_from_recovery_point("cp1")

        self.assertIsNotNone(result)
        self.assertEqual(result["checkpoint"], "cp1")
        self.assertEqual(result["state"]["step"], "load")

    def test_restore_nonexistent(self):
        """Test restoring a checkpoint that doesn't exist."""
        result = self.manager.restore_from_recovery_point("nonexistent")
        self.assertIsNone(result)

    def test_list_recovery_points(self):
        """Test listing recovery points."""
        self.manager.create_recovery_point("cp1", {"a": 1})
        self.manager.create_recovery_point("cp2", {"b": 2})
        points = self.manager.list_recovery_points()
        self.assertEqual(set(points), {"cp1", "cp2"})

    def test_delete_recovery_point(self):
        """Test deleting a recovery point."""
        self.manager.create_recovery_point("cp1", {"a": 1})
        self.assertTrue(self.manager.delete_recovery_point("cp1"))
        self.assertIsNone(self.manager.get_recovery_point("cp1"))

    def test_delete_nonexistent(self):
        """Test deleting a checkpoint that doesn't exist."""
        self.assertFalse(self.manager.delete_recovery_point("nonexistent"))


class TestGCSRecoveryManager(unittest.TestCase):
    """Test GCS-backed GCSRecoveryManager with mocked GCS client."""

    def setUp(self):
        self.mock_blob = MagicMock()
        self.mock_bucket = MagicMock()
        self.mock_bucket.blob.return_value = self.mock_blob

        self.mock_client = MagicMock()
        self.mock_client.bucket.return_value = self.mock_bucket

        self.storage_patcher = patch(
            "gcp_pipeline_core.data_deletion.recovery.GCSRecoveryManager._get_bucket"
        )
        self.mock_get_bucket = self.storage_patcher.start()
        self.mock_get_bucket.return_value = self.mock_bucket

        self.manager = GCSRecoveryManager(
            bucket_name="test-bucket",
            prefix="recovery_points/run_123",
        )

    def tearDown(self):
        self.storage_patcher.stop()

    def test_gcs_path(self):
        """Test GCS path generation."""
        path = self.manager._gcs_path("after_validation")
        self.assertEqual(path, "recovery_points/run_123/after_validation.json")

    def test_create_persists_to_gcs(self):
        """Test that create_recovery_point uploads to GCS."""
        rp = self.manager.create_recovery_point(
            "cp1", {"records": 100}
        )

        self.assertEqual(rp.checkpoint_name, "cp1")
        self.mock_bucket.blob.assert_called_with(
            "recovery_points/run_123/cp1.json"
        )
        self.mock_blob.upload_from_string.assert_called_once()

        # Verify JSON content
        uploaded = self.mock_blob.upload_from_string.call_args[0][0]
        data = json.loads(uploaded)
        self.assertEqual(data["checkpoint_name"], "cp1")
        self.assertEqual(data["state"]["records"], 100)

    def test_restore_from_memory_first(self):
        """Test that restore checks memory before GCS."""
        self.manager.create_recovery_point("cp1", {"step": "load"})

        # Reset mock to verify GCS is NOT called
        self.mock_blob.reset_mock()

        result = self.manager.restore_from_recovery_point("cp1")

        self.assertIsNotNone(result)
        self.assertEqual(result["state"]["step"], "load")
        # Should NOT have called download since it's in memory
        self.mock_blob.download_as_text.assert_not_called()

    def test_restore_from_gcs_when_not_in_memory(self):
        """Test that restore loads from GCS when not in memory."""
        self.mock_blob.exists.return_value = True
        self.mock_blob.download_as_text.return_value = json.dumps({
            "checkpoint_name": "cp1",
            "timestamp": "2026-03-16T12:00:00+00:00",
            "state": {"step": "transform"},
            "malformed_records": [],
        })

        result = self.manager.restore_from_recovery_point("cp1")

        self.assertIsNotNone(result)
        self.assertEqual(result["state"]["step"], "transform")
        self.mock_blob.download_as_text.assert_called_once()

        # Should now be cached in memory
        self.assertIn("cp1", self.manager.recovery_points)

    def test_restore_from_gcs_not_found(self):
        """Test restore when checkpoint doesn't exist in GCS."""
        self.mock_blob.exists.return_value = False

        result = self.manager.restore_from_recovery_point("nonexistent")

        self.assertIsNone(result)

    def test_delete_removes_from_gcs(self):
        """Test that delete removes from both memory and GCS."""
        self.manager.create_recovery_point("cp1", {"a": 1})
        self.mock_blob.exists.return_value = True

        result = self.manager.delete_recovery_point("cp1")

        self.assertTrue(result)
        self.mock_blob.delete.assert_called_once()
        self.assertIsNone(self.manager.get_recovery_point("cp1"))

    def test_list_includes_gcs(self):
        """Test that list combines memory and GCS checkpoints."""
        # One in memory
        self.manager.create_recovery_point("cp_memory", {"a": 1})

        # Two in GCS
        mock_blob1 = MagicMock()
        mock_blob1.name = "recovery_points/run_123/cp_gcs1.json"
        mock_blob2 = MagicMock()
        mock_blob2.name = "recovery_points/run_123/cp_gcs2.json"
        self.mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]

        points = self.manager.list_recovery_points()

        self.assertIn("cp_memory", points)
        self.assertIn("cp_gcs1", points)
        self.assertIn("cp_gcs2", points)

    def test_gcs_failure_on_create_is_non_fatal(self):
        """Test that GCS upload failure doesn't break create_recovery_point."""
        self.mock_blob.upload_from_string.side_effect = Exception("GCS unavailable")

        # Should still return the recovery point (in-memory)
        rp = self.manager.create_recovery_point("cp1", {"a": 1})

        self.assertEqual(rp.checkpoint_name, "cp1")
        self.assertIn("cp1", self.manager.recovery_points)


if __name__ == "__main__":
    unittest.main()

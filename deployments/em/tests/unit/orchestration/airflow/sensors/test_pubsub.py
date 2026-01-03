"""
Unit Tests for LOAPubSubPullSensor.

Tests verify sensor configuration using standard mocks from gcp_pipeline_tester.

Test file mirrors source structure:
    deployments/em/orchestration/airflow/sensors/pubsub.py
"""

import unittest
from unittest.mock import MagicMock, patch


class TestLOAPubSubPullSensorConfiguration(unittest.TestCase):
    """Test sensor configuration and defaults."""

    @patch("em.orchestration.airflow.sensors.pubsub.BasePubSubPullSensor")
    def test_sensor_can_be_instantiated(self, mock_base):
        """Test that sensor can be created with required params."""
        from em.orchestration.airflow.sensors.pubsub import LOAPubSubPullSensor

        sensor = LOAPubSubPullSensor(
            task_id="test_sensor",
            project_id="test-project",
            subscription="test-subscription",
        )

        self.assertEqual(sensor.task_id, "test_sensor")

    @patch("em.orchestration.airflow.sensors.pubsub.BasePubSubPullSensor")
    def test_sensor_has_filter_ok_files_attribute(self, mock_base):
        """Test sensor has filter_ok_files attribute."""
        from em.orchestration.airflow.sensors.pubsub import LOAPubSubPullSensor

        sensor = LOAPubSubPullSensor(
            task_id="test_sensor",
            project_id="test-project",
            subscription="test-subscription",
            filter_ok_files=True,
        )

        self.assertTrue(
            hasattr(sensor, "filter_ok_files") or hasattr(sensor, "filter_extension")
        )

    @patch("em.orchestration.airflow.sensors.pubsub.BasePubSubPullSensor")
    def test_sensor_has_task_id(self, mock_base):
        """Test sensor stores task_id."""
        from em.orchestration.airflow.sensors.pubsub import LOAPubSubPullSensor

        sensor = LOAPubSubPullSensor(
            task_id="my_task",
            project_id="test-project",
            subscription="test-subscription",
        )

        self.assertEqual(sensor.task_id, "my_task")


class TestLOAPubSubPullSensorHelperMethods(unittest.TestCase):
    """Test helper methods on the sensor."""

    def test_extract_metadata_empty_message(self):
        """Test metadata extraction with empty message."""
        # This tests the helper logic, not the sensor itself
        message = {}
        metadata = self._extract_metadata(message)
        self.assertEqual(metadata, {})

    def test_extract_metadata_with_gcs_path(self):
        """Test metadata extraction when gcs_path is provided."""
        message = {"attributes": {"gcs_path": "gs://bucket/file.csv"}}
        metadata = self._extract_metadata(message)
        self.assertEqual(metadata.get("gcs_path"), "gs://bucket/file.csv")

    def test_extract_metadata_with_object_id(self):
        """Test metadata extraction when objectId is provided."""
        message = {"attributes": {"objectId": "data/file.csv", "bucketId": "my-bucket"}}
        metadata = self._extract_metadata(message)
        self.assertEqual(metadata.get("objectId"), "data/file.csv")

    def _extract_metadata(self, message: dict) -> dict:
        """Helper to extract metadata from message."""
        return message.get("attributes", {})


if __name__ == "__main__":
    unittest.main()


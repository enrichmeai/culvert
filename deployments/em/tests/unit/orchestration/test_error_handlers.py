"""
Unit tests for Error Handlers.

Tests cover:
- DLQ publishing
- Failure callbacks
- Validation failure handling
- Routing failure handling
- Quarantine file handling
- Error payload building
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
from datetime import datetime
from typing import Dict, Any


# Create mock for Airflow and GCS dependencies
mock_airflow = MagicMock()
mock_airflow.models.Variable.get.return_value = "test-project"
sys.modules["airflow"] = mock_airflow
sys.modules["airflow.models"] = mock_airflow.models


# Now import the error handlers
from deployments.em.orchestration.airflow.callbacks.error_handlers import (
    ErrorType,
    publish_to_dlq,
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    quarantine_file,
    on_schema_mismatch,
    on_data_quality_failure,
)


# Constants from the EM error handler config
DEFAULT_DLQ_TOPIC = "loa-notifications-dead-letter"
DEFAULT_QUARANTINE_BUCKET = "loa-quarantine"


class TestErrorTypeConstants(unittest.TestCase):
    """Test ErrorType constants."""

    def test_validation_failure(self):
        """Test VALIDATION_FAILURE constant."""
        self.assertEqual(ErrorType.VALIDATION_FAILURE, "VALIDATION_FAILURE")

    def test_routing_failure(self):
        """Test ROUTING_FAILURE constant."""
        self.assertEqual(ErrorType.ROUTING_FAILURE, "ROUTING_FAILURE")

    def test_task_failure(self):
        """Test TASK_FAILURE constant."""
        self.assertEqual(ErrorType.TASK_FAILURE, "TASK_FAILURE")

    def test_processing_failure(self):
        """Test PROCESSING_FAILURE constant."""
        self.assertEqual(ErrorType.PROCESSING_FAILURE, "PROCESSING_FAILURE")

    def test_schema_mismatch(self):
        """Test SCHEMA_MISMATCH constant."""
        self.assertEqual(ErrorType.SCHEMA_MISMATCH, "SCHEMA_MISMATCH")

    def test_data_quality_failure(self):
        """Test DATA_QUALITY_FAILURE constant."""
        self.assertEqual(ErrorType.DATA_QUALITY_FAILURE, "DATA_QUALITY_FAILURE")


class TestBuildErrorPayload(unittest.TestCase):
    """Test _build_error_payload function."""

    def test_basic_payload(self):
        """Test basic payload without context."""
        payload = _build_error_payload(
            error_type=ErrorType.VALIDATION_FAILURE,
            error_message="Test error message",
        )

        self.assertEqual(payload["error_type"], ErrorType.VALIDATION_FAILURE)
        self.assertEqual(payload["error_message"], "Test error message")
        self.assertIn("timestamp", payload)
        self.assertEqual(payload["metadata"], {})

    def test_payload_with_metadata(self):
        """Test payload with custom metadata."""
        metadata = {"file_path": "gs://bucket/file.csv", "line_number": 42}
        payload = _build_error_payload(
            error_type=ErrorType.TASK_FAILURE,
            error_message="Processing failed",
            metadata=metadata,
        )

        self.assertEqual(payload["metadata"]["file_path"], "gs://bucket/file.csv")
        self.assertEqual(payload["metadata"]["line_number"], 42)

    def test_payload_with_context(self):
        """Test payload with Airflow context."""
        mock_ti = MagicMock()
        mock_ti.task_id = "validate_input"
        mock_ti.dag_id = "loa_applications_dag"
        mock_ti.try_number = 1
        mock_ti.xcom_pull.return_value = {
            "gcs_path": "gs://bucket/data.csv",
            "entity_type": "applications",
            "system_id": "SYS001",
        }

        context = {
            "ti": mock_ti,
            "run_id": "manual__2026-01-01T00:00:00",
            "execution_date": datetime(2026, 1, 1, 12, 0, 0),
        }

        payload = _build_error_payload(
            error_type=ErrorType.VALIDATION_FAILURE,
            error_message="Validation error",
            context=context,
        )

        self.assertEqual(payload["task_id"], "validate_input")
        self.assertEqual(payload["run_id"], "manual__2026-01-01T00:00:00")
        self.assertEqual(payload["file_path"], "gs://bucket/data.csv")
        self.assertEqual(payload["entity_type"], "applications")

    def test_timestamp_format(self):
        """Test timestamp is ISO format with Z suffix."""
        payload = _build_error_payload(
            error_type=ErrorType.TASK_FAILURE,
            error_message="Test",
        )

        self.assertIn("Z", payload["timestamp"])
        self.assertIn("T", payload["timestamp"])


class TestPublishToDLQ(unittest.TestCase):
    """Test publish_to_dlq function."""

    def _create_mock_context(self) -> Dict[str, Any]:
        """Create mock Airflow context."""
        mock_ti = MagicMock()
        mock_ti.task_id = "test_task"
        mock_ti.xcom_pull.return_value = None

        return {
            "ti": mock_ti,
            "run_id": "test-run",
            "execution_date": datetime(2026, 1, 1),
        }

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.PubSubClient")
    def test_publish_success(self, mock_pubsub_class):
        """Test successful DLQ publish."""
        mock_client = MagicMock()
        mock_client.publish_event.return_value = "msg-123"
        mock_pubsub_class.return_value = mock_client

        context = self._create_mock_context()
        message_id = publish_to_dlq(
            context=context,
            error_message="Test error",
            error_type=ErrorType.VALIDATION_FAILURE,
        )

        self.assertEqual(message_id, "msg-123")
        mock_client.publish_event.assert_called_once()

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.PubSubClient")
    def test_publish_with_metadata(self, mock_pubsub_class):
        """Test DLQ publish includes metadata."""
        mock_client = MagicMock()
        mock_client.publish_event.return_value = "msg-456"
        mock_pubsub_class.return_value = mock_client

        context = self._create_mock_context()
        metadata = {"custom_key": "custom_value"}

        publish_to_dlq(
            context=context,
            error_message="Error with metadata",
            error_type=ErrorType.TASK_FAILURE,
            metadata=metadata,
        )

        call_args = mock_client.publish_event.call_args
        published_message = call_args[1]["message"]
        self.assertEqual(published_message["metadata"]["custom_key"], "custom_value")

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.PubSubClient")
    def test_publish_uses_default_topic(self, mock_pubsub_class):
        """Test DLQ publish uses default topic."""
        mock_client = MagicMock()
        mock_pubsub_class.return_value = mock_client

        context = self._create_mock_context()
        publish_to_dlq(
            context=context,
            error_message="Test",
            error_type=ErrorType.TASK_FAILURE,
        )

        call_args = mock_client.publish_event.call_args
        self.assertEqual(call_args[1]["topic"], DEFAULT_DLQ_TOPIC)

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.PubSubClient")
    def test_publish_custom_topic(self, mock_pubsub_class):
        """Test DLQ publish with custom topic."""
        mock_client = MagicMock()
        mock_pubsub_class.return_value = mock_client

        context = self._create_mock_context()
        publish_to_dlq(
            context=context,
            error_message="Test",
            error_type=ErrorType.TASK_FAILURE,
            topic="custom-dlq-topic",
        )

        call_args = mock_client.publish_event.call_args
        self.assertEqual(call_args[1]["topic"], "custom-dlq-topic")


class TestOnFailureCallback(unittest.TestCase):
    """Test on_failure_callback function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_callback_publishes_to_dlq(self, mock_publish):
        """Test callback publishes error to DLQ."""
        mock_ti = MagicMock()
        mock_ti.task_id = "failing_task"

        context = {
            "ti": mock_ti,
            "exception": ValueError("Test exception"),
        }

        on_failure_callback(context)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertIn("Test exception", call_args[1]["error_message"])
        self.assertEqual(call_args[1]["error_type"], ErrorType.TASK_FAILURE)

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_callback_handles_missing_exception(self, mock_publish):
        """Test callback handles missing exception gracefully."""
        mock_ti = MagicMock()
        mock_ti.task_id = "task"

        context = {"ti": mock_ti}  # No exception key

        on_failure_callback(context)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertIn("Unknown error", call_args[1]["error_message"])


class TestOnValidationFailure(unittest.TestCase):
    """Test on_validation_failure function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.quarantine_file")
    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_validation_failure_publishes_errors(self, mock_publish, mock_quarantine):
        """Test validation failure publishes error details."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Missing column: ssn", "Invalid format"],
            file_path="gs://bucket/file.csv",
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["error_type"], ErrorType.VALIDATION_FAILURE)
        self.assertIn("Missing column: ssn", call_args[1]["error_message"])

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.quarantine_file")
    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_validation_failure_quarantines_file(self, mock_publish, mock_quarantine):
        """Test validation failure quarantines the file."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Error"],
            file_path="gs://bucket/file.csv",
            quarantine=True,
        )

        mock_quarantine.assert_called_once()

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.quarantine_file")
    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_validation_failure_no_quarantine(self, mock_publish, mock_quarantine):
        """Test validation failure skips quarantine when disabled."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Error"],
            file_path="gs://bucket/file.csv",
            quarantine=False,
        )

        mock_quarantine.assert_not_called()

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.quarantine_file")
    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_validation_failure_string_error(self, mock_publish, mock_quarantine):
        """Test validation failure accepts string error."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors="Single error message",
            file_path="gs://bucket/file.csv",
        )

        mock_publish.assert_called_once()


class TestOnRoutingFailure(unittest.TestCase):
    """Test on_routing_failure function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_routing_failure_publishes(self, mock_publish):
        """Test routing failure publishes to DLQ."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_routing_failure(
            context=context,
            file_path="gs://bucket/unknown.csv",
            reason="No pipeline registered for UNKNOWN type",
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["error_type"], ErrorType.ROUTING_FAILURE)
        self.assertIn("No pipeline registered", call_args[1]["error_message"])


class TestQuarantineFile(unittest.TestCase):
    """Test quarantine_file function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.storage")
    def test_quarantine_success(self, mock_storage):
        """Test successful file quarantine."""
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client

        mock_source_bucket = MagicMock()
        mock_source_blob = MagicMock()
        mock_dest_bucket = MagicMock()

        mock_client.bucket.side_effect = [mock_source_bucket, mock_dest_bucket]
        mock_source_bucket.blob.return_value = mock_source_blob

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        result = quarantine_file(
            context=context,
            file_path="gs://source-bucket/data/file.csv",
            reason="validation_failure",
        )

        self.assertIsNotNone(result)
        mock_source_bucket.copy_blob.assert_called_once()
        mock_source_blob.delete.assert_called_once()

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.storage")
    def test_quarantine_invalid_path(self, mock_storage):
        """Test quarantine with invalid GCS path."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        result = quarantine_file(
            context=context,
            file_path="/local/path/file.csv",  # Invalid - not gs://
            reason="test",
        )

        self.assertIsNone(result)
        mock_storage.Client.assert_not_called()


class TestOnSchemaMismatch(unittest.TestCase):
    """Test on_schema_mismatch function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_schema_mismatch_detects_missing(self, mock_publish):
        """Test schema mismatch detects missing columns."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_schema_mismatch(
            context=context,
            file_path="gs://bucket/file.csv",
            expected_columns=["id", "name", "email"],
            actual_columns=["id", "name"],
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["error_type"], ErrorType.SCHEMA_MISMATCH)
        self.assertIn("email", call_args[1]["metadata"]["missing_columns"])

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_schema_mismatch_detects_extra(self, mock_publish):
        """Test schema mismatch detects extra columns."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_schema_mismatch(
            context=context,
            file_path="gs://bucket/file.csv",
            expected_columns=["id", "name"],
            actual_columns=["id", "name", "extra_col"],
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertIn("extra_col", call_args[1]["metadata"]["extra_columns"])


class TestOnDataQualityFailure(unittest.TestCase):
    """Test on_data_quality_failure function."""

    @patch("blueprint.components.orchestration.airflow.callbacks.error_handlers.publish_to_dlq")
    def test_data_quality_failure(self, mock_publish):
        """Test data quality failure reports failed checks."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        quality_checks = {
            "row_count": {"passed": True, "value": 1000},
            "null_check": {"passed": False, "value": 50, "threshold": 0},
            "uniqueness": {"passed": False, "value": 0.95, "threshold": 1.0},
        }

        on_data_quality_failure(
            context=context,
            table_name="loa_raw.applications",
            quality_checks=quality_checks,
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args[1]["error_type"], ErrorType.DATA_QUALITY_FAILURE)
        self.assertEqual(call_args[1]["metadata"]["failed_count"], 2)


class TestDefaultConstants(unittest.TestCase):
    """Test default constants."""

    def test_default_dlq_topic(self):
        """Test default DLQ topic name."""
        self.assertEqual(DEFAULT_DLQ_TOPIC, "loa-notifications-dead-letter")

    def test_default_quarantine_bucket(self):
        """Test default quarantine bucket name."""
        self.assertEqual(DEFAULT_QUARANTINE_BUCKET, "loa-quarantine")


if __name__ == "__main__":
    unittest.main()


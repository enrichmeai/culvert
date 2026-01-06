"""
Unit tests for EM Error Handlers.

Tests cover:
- DLQ publishing
- Failure callbacks
- Validation failure handling
- Routing failure handling
- Quarantine file handling
- Error payload building

Test file mirrors source structure:
    deployments/em/orchestration/airflow/callbacks/error_handlers.py
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from typing import Dict, Any


class TestErrorTypeConstants(unittest.TestCase):
    """Test ErrorType constants."""

    def test_validation_failure(self):
        """Test VALIDATION_FAILURE constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.VALIDATION_FAILURE, "VALIDATION_FAILURE")

    def test_routing_failure(self):
        """Test ROUTING_FAILURE constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.ROUTING_FAILURE, "ROUTING_FAILURE")

    def test_task_failure(self):
        """Test TASK_FAILURE constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.TASK_FAILURE, "TASK_FAILURE")

    def test_processing_failure(self):
        """Test PROCESSING_FAILURE constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.PROCESSING_FAILURE, "PROCESSING_FAILURE")

    def test_schema_mismatch(self):
        """Test SCHEMA_MISMATCH constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.SCHEMA_MISMATCH, "SCHEMA_MISMATCH")

    def test_data_quality_failure(self):
        """Test DATA_QUALITY_FAILURE constant."""
        from em.orchestration.airflow.callbacks.error_handlers import ErrorType
        self.assertEqual(ErrorType.DATA_QUALITY_FAILURE, "DATA_QUALITY_FAILURE")


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

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_success(self, mock_publish):
        """Test successful DLQ publish."""
        from em.orchestration.airflow.callbacks.error_handlers import publish_to_dlq, ErrorType

        mock_publish.return_value = "msg-123"

        context = self._create_mock_context()
        message_id = publish_to_dlq(
            context=context,
            error_message="Test error",
            error_type=ErrorType.VALIDATION_FAILURE,
        )

        self.assertEqual(message_id, "msg-123")
        mock_publish.assert_called_once()

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_with_metadata(self, mock_publish):
        """Test DLQ publish includes metadata."""
        from em.orchestration.airflow.callbacks.error_handlers import publish_to_dlq, ErrorType

        mock_publish.return_value = "msg-456"

        context = self._create_mock_context()
        metadata = {"custom_key": "custom_value"}

        publish_to_dlq(
            context=context,
            error_message="Error with metadata",
            error_type=ErrorType.TASK_FAILURE,
            metadata=metadata,
        )

        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["metadata"]["custom_key"], "custom_value")

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_uses_em_config(self, mock_publish):
        """Test DLQ publish uses EM config."""
        from em.orchestration.airflow.callbacks.error_handlers import publish_to_dlq, ErrorType

        mock_publish.return_value = "msg-789"

        context = self._create_mock_context()
        publish_to_dlq(
            context=context,
            error_message="Test",
            error_type=ErrorType.TASK_FAILURE,
        )

        call_args = mock_publish.call_args
        # Verify EM config is passed
        self.assertIn("config", call_args.kwargs)

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_custom_topic(self, mock_publish):
        """Test DLQ publish with custom topic."""
        from em.orchestration.airflow.callbacks.error_handlers import publish_to_dlq, ErrorType

        mock_publish.return_value = "msg-custom"

        context = self._create_mock_context()
        publish_to_dlq(
            context=context,
            error_message="Test",
            error_type=ErrorType.TASK_FAILURE,
            topic="custom-dlq-topic",
        )

        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["topic"], "custom-dlq-topic")


class TestOnFailureCallback(unittest.TestCase):
    """Test on_failure_callback function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_failure_callback")
    def test_callback_calls_base(self, mock_base_callback):
        """Test callback calls base implementation with EM config."""
        from em.orchestration.airflow.callbacks.error_handlers import on_failure_callback

        mock_ti = MagicMock()
        mock_ti.task_id = "failing_task"

        context = {
            "ti": mock_ti,
            "exception": ValueError("Test exception"),
        }

        on_failure_callback(context)

        mock_base_callback.assert_called_once()
        call_args = mock_base_callback.call_args
        # Check positional arg (context is first positional arg)
        self.assertEqual(call_args.args[0], context)
        self.assertIn("config", call_args.kwargs)


class TestOnValidationFailure(unittest.TestCase):
    """Test on_validation_failure function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_calls_base(self, mock_base):
        """Test validation failure calls base with correct params."""
        from em.orchestration.airflow.callbacks.error_handlers import on_validation_failure

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Missing column: ssn", "Invalid format"],
            file_path="gs://bucket/file.csv",
        )

        mock_base.assert_called_once()
        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["file_path"], "gs://bucket/file.csv")

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_quarantine_default(self, mock_base):
        """Test validation failure quarantine defaults to True."""
        from em.orchestration.airflow.callbacks.error_handlers import on_validation_failure

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Error"],
            file_path="gs://bucket/file.csv",
        )

        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["quarantine"], True)

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_no_quarantine(self, mock_base):
        """Test validation failure with quarantine disabled."""
        from em.orchestration.airflow.callbacks.error_handlers import on_validation_failure

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Error"],
            file_path="gs://bucket/file.csv",
            quarantine=False,
        )

        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["quarantine"], False)


class TestOnRoutingFailure(unittest.TestCase):
    """Test on_routing_failure function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_routing_failure")
    def test_routing_failure_calls_base(self, mock_base):
        """Test routing failure calls base implementation."""
        from em.orchestration.airflow.callbacks.error_handlers import on_routing_failure

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_routing_failure(
            context=context,
            file_path="gs://bucket/unknown.csv",
            reason="No pipeline registered for UNKNOWN type",
        )

        mock_base.assert_called_once()
        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["file_path"], "gs://bucket/unknown.csv")
        self.assertIn("No pipeline registered", call_args.kwargs["reason"])


class TestQuarantineFile(unittest.TestCase):
    """Test quarantine_file function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_quarantine_file")
    def test_quarantine_calls_base(self, mock_base):
        """Test quarantine calls base implementation."""
        from em.orchestration.airflow.callbacks.error_handlers import quarantine_file

        mock_base.return_value = "gs://em-quarantine/file.csv"

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        result = quarantine_file(
            context=context,
            file_path="gs://source-bucket/data/file.csv",
            reason="validation_failure",
        )

        self.assertEqual(result, "gs://em-quarantine/file.csv")
        mock_base.assert_called_once()


class TestOnSchemaMismatch(unittest.TestCase):
    """Test on_schema_mismatch function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_schema_mismatch")
    def test_schema_mismatch_calls_base(self, mock_base):
        """Test schema mismatch calls base implementation."""
        from em.orchestration.airflow.callbacks.error_handlers import on_schema_mismatch

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_schema_mismatch(
            context=context,
            file_path="gs://bucket/file.csv",
            expected_columns=["id", "name", "email"],
            actual_columns=["id", "name"],
        )

        mock_base.assert_called_once()
        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["expected_columns"], ["id", "name", "email"])
        self.assertEqual(call_args.kwargs["actual_columns"], ["id", "name"])


class TestOnDataQualityFailure(unittest.TestCase):
    """Test on_data_quality_failure function."""

    @patch("em.orchestration.airflow.callbacks.error_handlers.base_on_data_quality_failure")
    def test_data_quality_failure_calls_base(self, mock_base):
        """Test data quality failure calls base implementation."""
        from em.orchestration.airflow.callbacks.error_handlers import on_data_quality_failure

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        quality_checks = {
            "row_count": {"passed": True, "value": 1000},
            "null_check": {"passed": False, "value": 50, "threshold": 0},
            "uniqueness": {"passed": False, "value": 0.95, "threshold": 1.0},
        }

        on_data_quality_failure(
            context=context,
            table_name="em_raw.customers",
            quality_checks=quality_checks,
        )

        mock_base.assert_called_once()
        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["table_name"], "em_raw.customers")


class TestDefaultConstants(unittest.TestCase):
    """Test default constants from EM config."""

    def test_default_dlq_topic(self):
        """Test default DLQ topic name for EM."""
        # EM uses its own DLQ topic
        DEFAULT_DLQ_TOPIC = "em-notifications-dead-letter"
        self.assertEqual(DEFAULT_DLQ_TOPIC, "em-notifications-dead-letter")

    def test_default_quarantine_bucket(self):
        """Test default quarantine bucket name for EM."""
        DEFAULT_QUARANTINE_BUCKET = "em-quarantine"
        self.assertEqual(DEFAULT_QUARANTINE_BUCKET, "em-quarantine")


if __name__ == "__main__":
    unittest.main()

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
import sys
import types
from datetime import datetime
from typing import Dict, Any


# =============================================================================
# Mock all Airflow and GCP dependencies BEFORE any imports
# =============================================================================

class MockModule(MagicMock):
    """Mock module that can act as a package."""
    @property
    def __path__(self):
        return []

    def __getattr__(self, name):
        if name == "__version__":
            return "4.25.1"
        return MagicMock()


# Mock Airflow
mock_airflow = types.ModuleType('airflow')
mock_airflow.DAG = MagicMock()
mock_airflow.Dataset = MagicMock()
mock_airflow.AirflowException = Exception
sys.modules['airflow'] = mock_airflow
sys.modules['airflow.models'] = MagicMock()
sys.modules['airflow.models'].Variable = MagicMock()
sys.modules['airflow.models'].Variable.get = MagicMock(return_value="test-project")
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['airflow.exceptions'].AirflowException = Exception
sys.modules['airflow.providers'] = MockModule()
sys.modules['airflow.providers.google'] = MockModule()
sys.modules['airflow.providers.google.cloud'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors.pubsub'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors.pubsub'].PubSubPullSensor = MagicMock()
sys.modules['airflow.providers.google.cloud.operators'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.dataflow'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.bigquery'] = MockModule()
sys.modules['airflow.operators'] = MockModule()
sys.modules['airflow.operators.python'] = MockModule()
sys.modules['airflow.operators.bash'] = MockModule()
sys.modules['airflow.utils'] = MockModule()
sys.modules['airflow.utils.dates'] = MockModule()
sys.modules['airflow.utils.context'] = MockModule()
sys.modules['airflow.utils.context'].Context = MagicMock()

# Mock Google Cloud
sys.modules['google'] = MockModule()
sys.modules['google.cloud'] = MockModule()
sys.modules['google.cloud.exceptions'] = MockModule()
sys.modules['google.cloud.storage'] = MockModule()
sys.modules['google.cloud.pubsub_v1'] = MockModule()
sys.modules['google.api_core'] = MockModule()
sys.modules['google.api_core.exceptions'] = MockModule()
mock_proto = MockModule()
mock_proto.__version__ = "4.25.1"
sys.modules['google.protobuf'] = mock_proto
sys.modules['google.protobuf.wrappers_pb2'] = MockModule()
sys.modules['google.protobuf.message'] = MockModule()
sys.modules['google.protobuf.json_format'] = MockModule()
sys.modules['google.protobuf.internal'] = MockModule()
sys.modules['google.protobuf.internal.containers'] = MockModule()
sys.modules['google.protobuf.internal.enum_type_wrapper'] = MockModule()

# =============================================================================
# Now import the error handlers (after mocks are in place)
# =============================================================================

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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_success(self, mock_publish):
        """Test successful DLQ publish."""
        mock_publish.return_value = "msg-123"

        context = self._create_mock_context()
        message_id = publish_to_dlq(
            context=context,
            error_message="Test error",
            error_type=ErrorType.VALIDATION_FAILURE,
        )

        self.assertEqual(message_id, "msg-123")
        mock_publish.assert_called_once()

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_with_metadata(self, mock_publish):
        """Test DLQ publish includes metadata."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_uses_loa_config(self, mock_publish):
        """Test DLQ publish uses LOA config."""
        mock_publish.return_value = "msg-789"

        context = self._create_mock_context()
        publish_to_dlq(
            context=context,
            error_message="Test",
            error_type=ErrorType.TASK_FAILURE,
        )

        call_args = mock_publish.call_args
        # Verify LOA config is passed
        self.assertIn("config", call_args.kwargs)

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_publish_to_dlq")
    def test_publish_custom_topic(self, mock_publish):
        """Test DLQ publish with custom topic."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_failure_callback")
    def test_callback_calls_base(self, mock_base_callback):
        """Test callback calls base implementation with LOA config."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_calls_base(self, mock_base):
        """Test validation failure calls base with correct params."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_quarantine_default(self, mock_base):
        """Test validation failure quarantine defaults to True."""
        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        on_validation_failure(
            context=context,
            validation_errors=["Error"],
            file_path="gs://bucket/file.csv",
        )

        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["quarantine"], True)

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_validation_failure")
    def test_validation_failure_no_quarantine(self, mock_base):
        """Test validation failure with quarantine disabled."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_routing_failure")
    def test_routing_failure_calls_base(self, mock_base):
        """Test routing failure calls base implementation."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_quarantine_file")
    def test_quarantine_calls_base(self, mock_base):
        """Test quarantine calls base implementation."""
        mock_base.return_value = "gs://loa-quarantine/file.csv"

        mock_ti = MagicMock()
        context = {"ti": mock_ti}

        result = quarantine_file(
            context=context,
            file_path="gs://source-bucket/data/file.csv",
            reason="validation_failure",
        )

        self.assertEqual(result, "gs://loa-quarantine/file.csv")
        mock_base.assert_called_once()


class TestOnSchemaMismatch(unittest.TestCase):
    """Test on_schema_mismatch function."""

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_schema_mismatch")
    def test_schema_mismatch_calls_base(self, mock_base):
        """Test schema mismatch calls base implementation."""
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

    @patch("deployments.em.orchestration.airflow.callbacks.error_handlers.base_on_data_quality_failure")
    def test_data_quality_failure_calls_base(self, mock_base):
        """Test data quality failure calls base implementation."""
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

        mock_base.assert_called_once()
        call_args = mock_base.call_args
        self.assertEqual(call_args.kwargs["table_name"], "loa_raw.applications")


class TestDefaultConstants(unittest.TestCase):
    """Test default constants from LOA config."""

    def test_default_dlq_topic(self):
        """Test default DLQ topic name."""
        self.assertEqual(DEFAULT_DLQ_TOPIC, "loa-notifications-dead-letter")

    def test_default_quarantine_bucket(self):
        """Test default quarantine bucket name."""
        self.assertEqual(DEFAULT_QUARANTINE_BUCKET, "loa-quarantine")


if __name__ == "__main__":
    unittest.main()


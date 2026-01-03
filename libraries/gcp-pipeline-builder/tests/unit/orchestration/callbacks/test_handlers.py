"""Unit tests for callback handlers."""

import unittest
from unittest.mock import MagicMock, patch

from gcp_pipeline_builder.orchestration.callbacks import (
    ErrorHandlerConfig,
    ErrorType,
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    on_schema_mismatch,
    on_data_quality_failure,
)


class TestOnFailureCallback(unittest.TestCase):
    """Test on_failure_callback function."""

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_failure_callback(self, mock_publish):
        """Test failure callback publishes to DLQ."""
        mock_ti = MagicMock()
        mock_ti.task_id = "test_task"

        context = {
            "ti": mock_ti,
            "exception": ValueError("Test error"),
        }

        on_failure_callback(context)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["error_type"], ErrorType.TASK_FAILURE)
        self.assertIn("Test error", call_args.kwargs["error_message"])


class TestOnValidationFailure(unittest.TestCase):
    """Test on_validation_failure function."""

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.quarantine_file')
    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_validation_failure(self, mock_publish, mock_quarantine):
        """Test validation failure handler."""
        context = {"ti": MagicMock()}
        errors = ["Error 1", "Error 2"]
        file_path = "gs://bucket/file.csv"

        on_validation_failure(context, errors, file_path)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["error_type"], ErrorType.VALIDATION_FAILURE)
        self.assertIn(file_path, call_args.kwargs["error_message"])

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.quarantine_file')
    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_validation_failure_with_string_error(self, mock_publish, mock_quarantine):
        """Test validation failure with single string error."""
        context = {"ti": MagicMock()}
        error = "Single error"
        file_path = "gs://bucket/file.csv"

        on_validation_failure(context, error, file_path)

        mock_publish.assert_called_once()


class TestOnRoutingFailure(unittest.TestCase):
    """Test on_routing_failure function."""

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_routing_failure(self, mock_publish):
        """Test routing failure handler."""
        context = {"ti": MagicMock()}
        file_path = "gs://bucket/file.csv"
        reason = "Unknown file type"

        on_routing_failure(context, file_path, reason)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["error_type"], ErrorType.ROUTING_FAILURE)


class TestOnSchemaMismatch(unittest.TestCase):
    """Test on_schema_mismatch function."""

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_schema_mismatch(self, mock_publish):
        """Test schema mismatch handler."""
        context = {"ti": MagicMock()}
        file_path = "gs://bucket/file.csv"
        expected = ["id", "name", "email"]
        actual = ["id", "name", "phone"]

        on_schema_mismatch(context, file_path, expected, actual)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["error_type"], ErrorType.SCHEMA_MISMATCH)


class TestOnDataQualityFailure(unittest.TestCase):
    """Test on_data_quality_failure function."""

    @patch('gcp_pipeline_builder.orchestration.callbacks.handlers.publish_to_dlq')
    def test_on_data_quality_failure(self, mock_publish):
        """Test data quality failure handler."""
        context = {"ti": MagicMock()}
        table_name = "my_table"
        quality_checks = {
            "null_check": {"passed": True},
            "range_check": {"passed": False, "error": "Out of range"},
        }

        on_data_quality_failure(context, table_name, quality_checks)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["error_type"], ErrorType.DATA_QUALITY_FAILURE)


if __name__ == '__main__':
    unittest.main()


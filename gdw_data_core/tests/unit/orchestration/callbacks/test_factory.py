"""Unit tests for ErrorHandler factory."""

import unittest
from unittest.mock import MagicMock, patch

from gdw_data_core.orchestration.callbacks import (
    ErrorHandlerConfig,
    create_error_handler,
)
from gdw_data_core.orchestration.callbacks.factory import ErrorHandler


class TestErrorHandler(unittest.TestCase):
    """Test ErrorHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ErrorHandlerConfig(
            dlq_topic="test-dlq",
            quarantine_bucket="test-quarantine",
        )
        self.handler = ErrorHandler(self.config)

    def test_handler_has_config(self):
        """Test handler stores config."""
        self.assertEqual(self.handler.config.dlq_topic, "test-dlq")
        self.assertEqual(self.handler.config.quarantine_bucket, "test-quarantine")

    @patch('gdw_data_core.orchestration.callbacks.factory.publish_to_dlq')
    def test_handler_publish_to_dlq(self, mock_publish):
        """Test handler's publish_to_dlq method."""
        context = {"ti": MagicMock()}

        self.handler.publish_to_dlq(context, "Test error")

        mock_publish.assert_called_once()
        # Verify config is passed
        self.assertEqual(mock_publish.call_args.args[-1], self.config)

    @patch('gdw_data_core.orchestration.callbacks.factory.on_failure_callback')
    def test_handler_on_failure_callback(self, mock_callback):
        """Test handler's on_failure_callback method."""
        context = {"ti": MagicMock()}

        self.handler.on_failure_callback(context)

        mock_callback.assert_called_once_with(context, self.config)


class TestCreateErrorHandler(unittest.TestCase):
    """Test create_error_handler factory function."""

    def test_create_error_handler(self):
        """Test creating error handler with config."""
        config = ErrorHandlerConfig(dlq_topic="my-dlq")
        handler = create_error_handler(config)

        self.assertIsInstance(handler, ErrorHandler)
        self.assertEqual(handler.config.dlq_topic, "my-dlq")


if __name__ == '__main__':
    unittest.main()


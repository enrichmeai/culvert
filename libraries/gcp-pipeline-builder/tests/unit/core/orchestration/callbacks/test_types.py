"""Unit tests for callback types."""

import unittest

from gcp_pipeline_builder.orchestration.callbacks import (
    ErrorHandlerConfig,
    ErrorType,
)
from gcp_pipeline_builder.orchestration.callbacks.types import (
    set_default_config,
    get_default_config,
)


class TestErrorHandlerConfig(unittest.TestCase):
    """Test ErrorHandlerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ErrorHandlerConfig()

        self.assertEqual(config.dlq_topic, "notifications-dead-letter")
        self.assertEqual(config.quarantine_bucket, "quarantine")
        self.assertEqual(config.project_id_var, "gcp_project_id")
        self.assertTrue(config.enable_quarantine)
        self.assertTrue(config.enable_dlq)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ErrorHandlerConfig(
            dlq_topic="my-custom-dlq",
            quarantine_bucket="my-quarantine",
            enable_dlq=False,
        )

        self.assertEqual(config.dlq_topic, "my-custom-dlq")
        self.assertEqual(config.quarantine_bucket, "my-quarantine")
        self.assertFalse(config.enable_dlq)


class TestErrorType(unittest.TestCase):
    """Test ErrorType constants."""

    def test_error_type_constants(self):
        """Test that all error type constants are defined."""
        self.assertEqual(ErrorType.VALIDATION_FAILURE, "VALIDATION_FAILURE")
        self.assertEqual(ErrorType.ROUTING_FAILURE, "ROUTING_FAILURE")
        self.assertEqual(ErrorType.TASK_FAILURE, "TASK_FAILURE")
        self.assertEqual(ErrorType.PROCESSING_FAILURE, "PROCESSING_FAILURE")
        self.assertEqual(ErrorType.SCHEMA_MISMATCH, "SCHEMA_MISMATCH")
        self.assertEqual(ErrorType.DATA_QUALITY_FAILURE, "DATA_QUALITY_FAILURE")


class TestDefaultConfig(unittest.TestCase):
    """Test default config functions."""

    def test_set_and_get_default_config(self):
        """Test setting and getting default config."""
        original = get_default_config()

        new_config = ErrorHandlerConfig(dlq_topic="test-topic")
        set_default_config(new_config)

        self.assertEqual(get_default_config().dlq_topic, "test-topic")

        # Restore original
        set_default_config(original)


if __name__ == '__main__':
    unittest.main()


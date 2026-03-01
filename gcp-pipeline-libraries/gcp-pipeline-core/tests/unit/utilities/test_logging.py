"""
Unit tests for Structured JSON Logging.

Tests the StructuredLogger, StructuredJsonFormatter, and configure_structured_logging.
"""

import json
import logging
import unittest
from io import StringIO

from gcp_pipeline_core.utilities.logging import (
    StructuredLogger,
    StructuredJsonFormatter,
    configure_structured_logging,
    get_logger,
)


class TestStructuredJsonFormatter(unittest.TestCase):
    """Tests for StructuredJsonFormatter."""

    def setUp(self):
        """Set up test logger with StringIO capture."""
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(StructuredJsonFormatter())

        self.logger = logging.getLogger("test_formatter")
        self.logger.handlers.clear()
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)

    def tearDown(self):
        """Clean up logger."""
        self.logger.handlers.clear()

    def test_outputs_valid_json(self):
        """Log output should be valid JSON."""
        self.logger.info("Test message")
        output = self.stream.getvalue().strip()

        # Should not raise
        log_entry = json.loads(output)
        self.assertIsInstance(log_entry, dict)

    def test_includes_standard_fields(self):
        """Log entry should include standard fields."""
        self.logger.info("Test message")
        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertIn('timestamp', log_entry)
        self.assertIn('level', log_entry)
        self.assertIn('message', log_entry)
        self.assertIn('logger', log_entry)
        self.assertIn('module', log_entry)

    def test_level_is_correct(self):
        """Log level should be correct."""
        self.logger.warning("Warning message")
        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['level'], 'WARNING')

    def test_message_is_correct(self):
        """Log message should be correct."""
        self.logger.info("My test message")
        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['message'], 'My test message')

    def test_extra_fields_included(self):
        """Extra fields should be included in log entry."""
        self.logger.info("Test message", extra={'records': 100, 'stage': 'validation'})
        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['records'], 100)
        self.assertEqual(log_entry['stage'], 'validation')


class TestStructuredLogger(unittest.TestCase):
    """Tests for StructuredLogger class."""

    def setUp(self):
        """Set up test logger with StringIO capture."""
        self.stream = StringIO()

    def test_creates_logger(self):
        """StructuredLogger should create successfully."""
        logger = StructuredLogger(
            name="test_structured",
            run_id="run_123",
            system_id="Application1"
        )
        self.assertIsNotNone(logger)
        self.assertEqual(logger.run_id, "run_123")
        self.assertEqual(logger.system_id, "Application1")

    def test_log_info(self):
        """info() should log at INFO level."""
        logger = configure_structured_logging(
            run_id="test_run",
            system_id="Application1",
            logger_name="test_info",
            stream=self.stream
        )
        logger.info("Test info message")

        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['level'], 'INFO')
        self.assertEqual(log_entry['message'], 'Test info message')

    def test_log_with_extra_fields(self):
        """Logger should include extra fields."""
        logger = configure_structured_logging(
            run_id="test_run",
            system_id="Application1",
            logger_name="test_extra",
            stream=self.stream
        )
        logger.info("Processing", records=500, stage="parse")

        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['records'], 500)
        self.assertEqual(log_entry['stage'], 'parse')

    def test_context_included(self):
        """Context (run_id, system_id) should be included."""
        logger = configure_structured_logging(
            run_id="application1_20260105_123456",
            system_id="Application1",
            entity_type="customers",
            logger_name="test_context",
            stream=self.stream
        )
        logger.info("Test message")

        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['run_id'], 'application1_20260105_123456')
        self.assertEqual(log_entry['system_id'], 'Application1')
        self.assertEqual(log_entry['entity_type'], 'customers')

    def test_set_context(self):
        """set_context should update context."""
        logger = configure_structured_logging(
            run_id="initial_run",
            system_id="Application1",
            logger_name="test_set_context",
            stream=self.stream
        )

        logger.set_context(entity_type="accounts")
        logger.info("After context update")

        output = self.stream.getvalue().strip()
        log_entry = json.loads(output)

        self.assertEqual(log_entry['entity_type'], 'accounts')

    def test_all_log_levels(self):
        """All log levels should work."""
        logger = configure_structured_logging(
            logger_name="test_levels",
            stream=self.stream,
            level=logging.DEBUG
        )

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        lines = self.stream.getvalue().strip().split('\n')
        self.assertEqual(len(lines), 4)

        levels = [json.loads(line)['level'] for line in lines]
        self.assertEqual(levels, ['DEBUG', 'INFO', 'WARNING', 'ERROR'])


class TestConfigureStructuredLogging(unittest.TestCase):
    """Tests for configure_structured_logging function."""

    def test_returns_structured_logger(self):
        """Should return StructuredLogger instance."""
        stream = StringIO()
        logger = configure_structured_logging(
            run_id="test",
            logger_name="test_return",
            stream=stream
        )
        self.assertIsInstance(logger, StructuredLogger)

    def test_configures_json_output(self):
        """Should configure JSON output format."""
        stream = StringIO()
        logger = configure_structured_logging(
            logger_name="test_json_config",
            stream=stream
        )
        logger.info("Test")

        output = stream.getvalue().strip()
        # Should be valid JSON
        self.assertTrue(output.startswith('{'))
        self.assertTrue(output.endswith('}'))

    def test_no_duplicate_handlers(self):
        """Calling twice should not create duplicate handlers."""
        stream = StringIO()

        # Call twice
        configure_structured_logging(logger_name="test_dup", stream=stream)
        logger = configure_structured_logging(logger_name="test_dup", stream=stream)

        logger.info("Single message")

        lines = stream.getvalue().strip().split('\n')
        # Should only have one line, not two
        self.assertEqual(len(lines), 1)


class TestGetLogger(unittest.TestCase):
    """Tests for get_logger function."""

    def test_get_logger_returns_structured_logger(self):
        """get_logger should return StructuredLogger."""
        logger = get_logger("test_get")
        self.assertIsInstance(logger, StructuredLogger)

    def test_get_logger_uses_name(self):
        """get_logger should use provided name."""
        logger = get_logger("my_custom_logger")
        self.assertEqual(logger.name, "my_custom_logger")


if __name__ == '__main__':
    unittest.main()


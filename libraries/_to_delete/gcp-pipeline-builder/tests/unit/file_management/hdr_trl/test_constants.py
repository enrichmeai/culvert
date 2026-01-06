"""Unit tests for HDR/TRL constants."""

import unittest

from gcp_pipeline_builder.file_management.hdr_trl import (
    DEFAULT_HDR_PATTERN,
    DEFAULT_TRL_PATTERN,
    DEFAULT_HDR_PREFIX,
    DEFAULT_TRL_PREFIX,
    DEFAULT_PARSER_CONFIG,
)


class TestDefaultConstants(unittest.TestCase):
    """Test that default constants are correct."""

    def test_default_hdr_pattern(self):
        """Test DEFAULT_HDR_PATTERN is correct."""
        self.assertEqual(
            DEFAULT_HDR_PATTERN,
            r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
        )

    def test_default_trl_pattern(self):
        """Test DEFAULT_TRL_PATTERN is correct."""
        self.assertEqual(
            DEFAULT_TRL_PATTERN,
            r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
        )

    def test_default_hdr_prefix(self):
        """Test DEFAULT_HDR_PREFIX is correct."""
        self.assertEqual(DEFAULT_HDR_PREFIX, "HDR|")

    def test_default_trl_prefix(self):
        """Test DEFAULT_TRL_PREFIX is correct."""
        self.assertEqual(DEFAULT_TRL_PREFIX, "TRL|")

    def test_default_parser_config(self):
        """Test DEFAULT_PARSER_CONFIG contains all required keys."""
        self.assertIn("hdr_pattern", DEFAULT_PARSER_CONFIG)
        self.assertIn("trl_pattern", DEFAULT_PARSER_CONFIG)
        self.assertIn("hdr_prefix", DEFAULT_PARSER_CONFIG)
        self.assertIn("trl_prefix", DEFAULT_PARSER_CONFIG)

        self.assertEqual(DEFAULT_PARSER_CONFIG["hdr_pattern"], DEFAULT_HDR_PATTERN)
        self.assertEqual(DEFAULT_PARSER_CONFIG["trl_pattern"], DEFAULT_TRL_PATTERN)


if __name__ == '__main__':
    unittest.main()


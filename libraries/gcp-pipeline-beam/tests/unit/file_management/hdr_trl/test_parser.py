"""Unit tests for HDR/TRL Parser."""

import unittest

from gcp_pipeline_beam.file_management.hdr_trl import (
    HDRTRLParser,
    HeaderRecord,
    TrailerRecord,
)


class TestHDRTRLParserDefaults(unittest.TestCase):
    """Test HDRTRLParser with default patterns."""

    def setUp(self):
        """Set up parser for tests."""
        self.parser = HDRTRLParser()

    def test_parse_valid_header(self):
        """Test parsing a valid header line."""
        line = "HDR|EM|Customer|20260101"
        result = self.parser.parse_header(line)

        self.assertIsNotNone(result)
        self.assertEqual(result.system_id, "EM")
        self.assertEqual(result.entity_type, "Customer")
        self.assertEqual(result.extract_date, "20260101")

    def test_parse_valid_header_with_whitespace(self):
        """Test parsing header with leading/trailing whitespace."""
        line = "  HDR|LOA|Applications|20260115  \n"
        result = self.parser.parse_header(line)

        self.assertIsNotNone(result)
        self.assertEqual(result.system_id, "LOA")
        self.assertEqual(result.entity_type, "Applications")

    def test_parse_valid_trailer(self):
        """Test parsing a valid trailer line."""
        line = "TRL|RecordCount=5000|Checksum=a1b2c3d4"
        result = self.parser.parse_trailer(line)

        self.assertIsNotNone(result)
        self.assertEqual(result.record_count, 5000)
        self.assertEqual(result.checksum, "a1b2c3d4")

    def test_parse_trailer_with_large_count(self):
        """Test parsing trailer with large record count."""
        line = "TRL|RecordCount=1000000|Checksum=xyz789"
        result = self.parser.parse_trailer(line)

        self.assertIsNotNone(result)
        self.assertEqual(result.record_count, 1000000)

    def test_parse_invalid_header(self):
        """Test parsing invalid header returns None."""
        line = "INVALID|Header|Line"
        result = self.parser.parse_header(line)
        self.assertIsNone(result)

    def test_parse_invalid_trailer(self):
        """Test parsing invalid trailer returns None."""
        line = "INVALID|Trailer|Line"
        result = self.parser.parse_trailer(line)
        self.assertIsNone(result)

    def test_parse_file_lines(self):
        """Test parsing complete file lines."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "TRL|RecordCount=2|Checksum=abc123"
        ]

        metadata = self.parser.parse_file_lines(lines)

        self.assertEqual(metadata.header.system_id, "EM")
        self.assertEqual(metadata.trailer.record_count, 2)
        self.assertEqual(metadata.data_start_line, 1)
        self.assertEqual(metadata.data_end_line, 3)

    def test_parse_file_lines_empty_file(self):
        """Test parsing empty file raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.parser.parse_file_lines([])

        self.assertIn("Empty file", str(context.exception))

    def test_parse_file_lines_invalid_header(self):
        """Test parsing file with invalid header raises ValueError."""
        lines = [
            "NOT_A_HEADER",
            "id,name,ssn",
            "TRL|RecordCount=0|Checksum=abc123"
        ]

        with self.assertRaises(ValueError) as context:
            self.parser.parse_file_lines(lines)

        self.assertIn("Invalid header", str(context.exception))

    def test_parse_file_lines_invalid_trailer(self):
        """Test parsing file with invalid trailer raises ValueError."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "NOT_A_TRAILER"
        ]

        with self.assertRaises(ValueError) as context:
            self.parser.parse_file_lines(lines)

        self.assertIn("Invalid trailer", str(context.exception))

    def test_is_header_line(self):
        """Test is_header_line detection."""
        self.assertTrue(self.parser.is_header_line("HDR|EM|Customer|20260101"))
        self.assertTrue(self.parser.is_header_line("  HDR|test"))
        self.assertFalse(self.parser.is_header_line("TRL|something"))
        self.assertFalse(self.parser.is_header_line("id,name,ssn"))

    def test_is_trailer_line(self):
        """Test is_trailer_line detection."""
        self.assertTrue(self.parser.is_trailer_line("TRL|RecordCount=5|Checksum=abc"))
        self.assertTrue(self.parser.is_trailer_line("  TRL|test"))
        self.assertFalse(self.parser.is_trailer_line("HDR|something"))
        self.assertFalse(self.parser.is_trailer_line("id,name,ssn"))


class TestHDRTRLParserCustomPatterns(unittest.TestCase):
    """Test HDRTRLParser with custom patterns (non-default)."""

    def test_custom_patterns(self):
        """Test parser with custom patterns."""
        parser = HDRTRLParser(
            hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
            trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
            hdr_prefix="HEADER:",
            trl_prefix="FOOTER:"
        )

        # Test custom header
        header = parser.parse_header("HEADER:MY_SYSTEM:MY_ENTITY:20260101")
        self.assertIsNotNone(header)
        self.assertEqual(header.system_id, "MY_SYSTEM")
        self.assertEqual(header.entity_type, "MY_ENTITY")

        # Test custom trailer
        trailer = parser.parse_trailer("FOOTER:COUNT=100:HASH=xyz789")
        self.assertIsNotNone(trailer)
        self.assertEqual(trailer.record_count, 100)
        self.assertEqual(trailer.checksum, "xyz789")

        # Test line detection with custom prefix
        self.assertTrue(parser.is_header_line("HEADER:test"))
        self.assertTrue(parser.is_trailer_line("FOOTER:test"))
        self.assertFalse(parser.is_header_line("HDR|test"))  # Default pattern should not match

    def test_default_patterns_still_work(self):
        """Test that default patterns work without any arguments."""
        parser = HDRTRLParser()  # No arguments - use defaults

        header = parser.parse_header("HDR|EM|Customer|20260101")
        self.assertIsNotNone(header)
        self.assertEqual(header.system_id, "EM")

        trailer = parser.parse_trailer("TRL|RecordCount=500|Checksum=abc123")
        self.assertIsNotNone(trailer)
        self.assertEqual(trailer.record_count, 500)


if __name__ == '__main__':
    unittest.main()


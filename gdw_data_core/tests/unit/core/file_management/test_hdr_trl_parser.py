"""Unit tests for HDR/TRL parser."""

import unittest
from datetime import datetime

from gdw_data_core.core.file_management import (
    HDRTRLParser,
    HeaderRecord,
    TrailerRecord,
    ParsedFileMetadata,
)


class TestHeaderRecord(unittest.TestCase):
    """Test HeaderRecord dataclass."""

    def test_header_record_creation(self):
        """Test creating a HeaderRecord."""
        header = HeaderRecord(
            record_type="HDR",
            system_id="EM",
            entity_type="Customer",
            extract_date="20260101",
            raw_line="HDR|EM|Customer|20260101"
        )

        self.assertEqual(header.record_type, "HDR")
        self.assertEqual(header.system_id, "EM")
        self.assertEqual(header.entity_type, "Customer")
        self.assertEqual(header.extract_date, "20260101")

    def test_extract_date_parsed_property(self):
        """Test extract_date_parsed property."""
        header = HeaderRecord(
            record_type="HDR",
            system_id="EM",
            entity_type="Customer",
            extract_date="20260101",
            raw_line="HDR|EM|Customer|20260101"
        )

        parsed_date = header.extract_date_parsed
        self.assertIsInstance(parsed_date, datetime)
        self.assertEqual(parsed_date.year, 2026)
        self.assertEqual(parsed_date.month, 1)
        self.assertEqual(parsed_date.day, 1)


class TestTrailerRecord(unittest.TestCase):
    """Test TrailerRecord dataclass."""

    def test_trailer_record_creation(self):
        """Test creating a TrailerRecord."""
        trailer = TrailerRecord(
            record_type="TRL",
            record_count=5000,
            checksum="a1b2c3d4",
            raw_line="TRL|RecordCount=5000|Checksum=a1b2c3d4"
        )

        self.assertEqual(trailer.record_type, "TRL")
        self.assertEqual(trailer.record_count, 5000)
        self.assertEqual(trailer.checksum, "a1b2c3d4")


class TestHDRTRLParser(unittest.TestCase):
    """Test HDRTRLParser class."""

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
        line = "TRL|RecordCount=1000000|Checksum=abc123def456"
        result = self.parser.parse_trailer(line)

        self.assertIsNotNone(result)
        self.assertEqual(result.record_count, 1000000)

    def test_parse_invalid_header(self):
        """Test parsing an invalid header line returns None."""
        line = "INVALID|Header|Line"
        result = self.parser.parse_header(line)
        self.assertIsNone(result)

    def test_parse_invalid_header_missing_date(self):
        """Test parsing header missing date."""
        line = "HDR|EM|Customer"
        result = self.parser.parse_header(line)
        self.assertIsNone(result)

    def test_parse_invalid_trailer(self):
        """Test parsing an invalid trailer line returns None."""
        line = "TRL|InvalidFormat"
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


if __name__ == '__main__':
    unittest.main()


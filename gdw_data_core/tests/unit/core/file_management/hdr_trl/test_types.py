"""Unit tests for HDR/TRL types."""

import unittest
from datetime import datetime

from gdw_data_core.core.file_management.hdr_trl import (
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

    def test_header_with_extra_fields(self):
        """Test HeaderRecord with extra fields."""
        header = HeaderRecord(
            record_type="HDR",
            system_id="EM",
            entity_type="Customer",
            extract_date="20260101",
            raw_line="HDR|EM|Customer|20260101",
            extra_fields={"custom_field": "value"}
        )

        self.assertEqual(header.extra_fields["custom_field"], "value")


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

    def test_trailer_with_extra_fields(self):
        """Test TrailerRecord with extra fields."""
        trailer = TrailerRecord(
            record_type="TRL",
            record_count=100,
            checksum="xyz789",
            raw_line="TRL|RecordCount=100|Checksum=xyz789",
            extra_fields={"hash_algorithm": "md5"}
        )

        self.assertEqual(trailer.extra_fields["hash_algorithm"], "md5")


class TestParsedFileMetadata(unittest.TestCase):
    """Test ParsedFileMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating ParsedFileMetadata."""
        header = HeaderRecord(
            record_type="HDR",
            system_id="EM",
            entity_type="Customer",
            extract_date="20260101",
            raw_line="HDR|EM|Customer|20260101"
        )
        trailer = TrailerRecord(
            record_type="TRL",
            record_count=100,
            checksum="abc123",
            raw_line="TRL|RecordCount=100|Checksum=abc123"
        )

        metadata = ParsedFileMetadata(
            header=header,
            trailer=trailer,
            data_start_line=1,
            data_end_line=100
        )

        self.assertEqual(metadata.header.system_id, "EM")
        self.assertEqual(metadata.trailer.record_count, 100)
        self.assertEqual(metadata.data_start_line, 1)
        self.assertEqual(metadata.data_end_line, 100)


if __name__ == '__main__':
    unittest.main()


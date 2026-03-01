"""Unit tests for record count validator."""

import unittest

from gcp_pipeline_beam.file_management import validate_record_count


class TestValidateRecordCount(unittest.TestCase):
    """Test validate_record_count function."""

    def test_valid_record_count_with_csv_header(self):
        """Test valid record count with CSV header row."""
        lines = [
            "HDR|Application1|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "TRL|RecordCount=2|Checksum=abc123"
        ]

        is_valid, msg = validate_record_count(lines, 2, has_csv_header=True)

        self.assertTrue(is_valid)
        self.assertIn("valid", msg.lower())
        self.assertIn("2", msg)

    def test_valid_record_count_without_csv_header(self):
        """Test valid record count without CSV header row."""
        lines = [
            "HDR|Application1|Customer|20260101",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "TRL|RecordCount=2|Checksum=abc123"
        ]

        is_valid, msg = validate_record_count(lines, 2, has_csv_header=False)

        self.assertTrue(is_valid)

    def test_invalid_record_count_too_few(self):
        """Test invalid record count - fewer records than expected."""
        lines = [
            "HDR|Application1|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "TRL|RecordCount=5|Checksum=abc123"
        ]

        is_valid, msg = validate_record_count(lines, 5, has_csv_header=True)

        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())
        self.assertIn("expected 5", msg)

    def test_invalid_record_count_too_many(self):
        """Test invalid record count - more records than expected."""
        lines = [
            "HDR|Application1|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "1003,Bob,111-22-3333",
            "TRL|RecordCount=2|Checksum=abc123"
        ]

        is_valid, msg = validate_record_count(lines, 2, has_csv_header=True)

        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())

    def test_zero_records_expected_and_found(self):
        """Test file with no data records."""
        lines = [
            "HDR|Application1|Customer|20260101",
            "id,name,ssn",
            "TRL|RecordCount=0|Checksum=abc123"
        ]

        is_valid, msg = validate_record_count(lines, 0, has_csv_header=True)

        self.assertTrue(is_valid)

    def test_large_record_count(self):
        """Test validation with large record count."""
        # Create a file with 1000 data records
        lines = ["HDR|Application1|Customer|20260101", "id,name,ssn"]
        lines.extend([f"{i},Name{i},SSN{i}" for i in range(1000)])
        lines.append("TRL|RecordCount=1000|Checksum=abc123")

        is_valid, msg = validate_record_count(lines, 1000, has_csv_header=True)

        self.assertTrue(is_valid)


if __name__ == '__main__':
    unittest.main()


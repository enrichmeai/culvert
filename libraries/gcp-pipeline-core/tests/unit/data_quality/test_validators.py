"""Unit tests for duplicate key and row type validators."""

import unittest

from gcp_pipeline_core.data_quality import (
    check_duplicate_keys,
    validate_row_types,
)


class TestCheckDuplicateKeys(unittest.TestCase):
    """Test check_duplicate_keys function."""

    def test_no_duplicates(self):
        """Test with no duplicate keys."""
        records = [
            {"id": "1", "name": "John"},
            {"id": "2", "name": "Jane"},
            {"id": "3", "name": "Bob"},
        ]

        has_dups, dups = check_duplicate_keys(records, ["id"])

        self.assertFalse(has_dups)
        self.assertEqual(len(dups), 0)

    def test_single_duplicate(self):
        """Test with single duplicate key."""
        records = [
            {"id": "1", "name": "John"},
            {"id": "1", "name": "Jane"},  # Duplicate id
            {"id": "2", "name": "Bob"},
        ]

        has_dups, dups = check_duplicate_keys(records, ["id"])

        self.assertTrue(has_dups)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["key"], {"id": "1"})
        self.assertEqual(dups[0]["count"], 2)

    def test_multiple_duplicates(self):
        """Test with multiple duplicate keys."""
        records = [
            {"id": "1", "name": "John"},
            {"id": "1", "name": "Jane"},
            {"id": "2", "name": "Bob"},
            {"id": "2", "name": "Alice"},
            {"id": "3", "name": "Charlie"},
        ]

        has_dups, dups = check_duplicate_keys(records, ["id"])

        self.assertTrue(has_dups)
        self.assertEqual(len(dups), 2)

    def test_triple_duplicate(self):
        """Test with triple occurrence of same key."""
        records = [
            {"id": "1", "name": "John"},
            {"id": "1", "name": "Jane"},
            {"id": "1", "name": "Bob"},
        ]

        has_dups, dups = check_duplicate_keys(records, ["id"])

        self.assertTrue(has_dups)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["count"], 3)

    def test_composite_key(self):
        """Test with composite key (multiple fields)."""
        records = [
            {"date": "2026-01-01", "type": "A", "value": 100},
            {"date": "2026-01-01", "type": "B", "value": 200},
            {"date": "2026-01-01", "type": "A", "value": 300},  # Duplicate
            {"date": "2026-01-02", "type": "A", "value": 400},  # Different date
        ]

        has_dups, dups = check_duplicate_keys(records, ["date", "type"])

        self.assertTrue(has_dups)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["key"], {"date": "2026-01-01", "type": "A"})

    def test_empty_records(self):
        """Test with empty records list."""
        records = []

        has_dups, dups = check_duplicate_keys(records, ["id"])

        self.assertFalse(has_dups)
        self.assertEqual(len(dups), 0)

    def test_missing_key_field(self):
        """Test with missing key field in some records."""
        records = [
            {"id": "1", "name": "John"},
            {"name": "Jane"},  # Missing id
            {"id": "1", "name": "Bob"},
        ]

        has_dups, dups = check_duplicate_keys(records, ["id"])

        # The record with missing id will have None as key
        self.assertTrue(has_dups)


class TestValidateRowTypes(unittest.TestCase):
    """Test validate_row_types function."""

    def test_valid_file_structure(self):
        """Test valid file with HDR, data, and TRL."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "TRL|RecordCount=2|Checksum=abc123"
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertTrue(is_valid)
        self.assertIn("valid", msg.lower())

    def test_missing_hdr(self):
        """Test file missing HDR record."""
        lines = [
            "id,name,ssn",
            "1001,John,123-45-6789",
            "TRL|RecordCount=1|Checksum=abc123"
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertFalse(is_valid)
        self.assertIn("not header record", msg)

    def test_missing_trl(self):
        """Test file missing TRL record."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertFalse(is_valid)
        self.assertIn("not trailer record", msg)

    def test_hdr_in_middle(self):
        """Test file with HDR in middle."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "HDR|EM|Account|20260101",  # Unexpected HDR
            "1001,John,123-45-6789",
            "TRL|RecordCount=1|Checksum=abc123"
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertFalse(is_valid)
        self.assertIn("Unexpected header", msg)

    def test_trl_in_middle(self):
        """Test file with TRL in middle."""
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "TRL|RecordCount=1|Checksum=abc",  # Unexpected TRL
            "1001,John,123-45-6789",
            "TRL|RecordCount=1|Checksum=abc123"
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertFalse(is_valid)
        self.assertIn("Unexpected trailer", msg)

    def test_empty_file(self):
        """Test empty file."""
        lines = []

        is_valid, msg = validate_row_types(lines)

        self.assertFalse(is_valid)
        self.assertIn("Empty file", msg)

    def test_hdr_trl_only(self):
        """Test file with only HDR and TRL (no data)."""
        lines = [
            "HDR|EM|Customer|20260101",
            "TRL|RecordCount=0|Checksum=abc123"
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertTrue(is_valid)

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        lines = [
            "  HDR|EM|Customer|20260101  ",
            "id,name,ssn",
            "  TRL|RecordCount=0|Checksum=abc123  "
        ]

        is_valid, msg = validate_row_types(lines)

        self.assertTrue(is_valid)


if __name__ == '__main__':
    unittest.main()


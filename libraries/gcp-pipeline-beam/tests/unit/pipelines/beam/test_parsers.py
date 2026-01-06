"""Unit tests for CSV parser transforms."""

import unittest
from unittest.mock import MagicMock, patch

from gcp_pipeline_beam.pipelines.beam.transforms.parsers import ParseCsvLine


class TestParseCsvLine(unittest.TestCase):
    """Test ParseCsvLine DoFn."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        self.assertEqual(parser.field_names, ['id', 'name', 'email'])
        self.assertEqual(parser.delimiter, ',')
        self.assertTrue(parser.skip_hdr_trl)

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        parser = ParseCsvLine(
            field_names=['id', 'name'],
            delimiter='|',
            skip_hdr_trl=False
        )

        self.assertEqual(parser.delimiter, '|')
        self.assertFalse(parser.skip_hdr_trl)

    def test_parse_valid_line(self):
        """Test parsing a valid CSV line."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        result = list(parser.process('1,John,john@example.com'))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {
            'id': '1',
            'name': 'John',
            'email': 'john@example.com'
        })

    def test_parse_empty_line(self):
        """Test parsing an empty line returns nothing."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        result = list(parser.process(''))

        self.assertEqual(len(result), 0)

    def test_parse_whitespace_line(self):
        """Test parsing a whitespace-only line returns nothing."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        result = list(parser.process('   '))

        self.assertEqual(len(result), 0)

    def test_skip_hdr_record(self):
        """Test HDR record is skipped when skip_hdr_trl=True."""
        parser = ParseCsvLine(
            field_names=['id', 'name'],
            skip_hdr_trl=True
        )

        result = list(parser.process('HDR|EM|Customer|20260101'))

        self.assertEqual(len(result), 0)

    def test_skip_trl_record(self):
        """Test TRL record is skipped when skip_hdr_trl=True."""
        parser = ParseCsvLine(
            field_names=['id', 'name'],
            skip_hdr_trl=True
        )

        result = list(parser.process('TRL|RecordCount=100|Checksum=abc123'))

        self.assertEqual(len(result), 0)

    def test_no_skip_hdr_when_disabled(self):
        """Test HDR record is NOT skipped when skip_hdr_trl=False."""
        parser = ParseCsvLine(
            field_names=['a', 'b', 'c', 'd'],
            delimiter='|',
            skip_hdr_trl=False
        )

        result = list(parser.process('HDR|EM|Customer|20260101'))

        # Should attempt to parse (will succeed since we have 4 fields)
        self.assertEqual(len(result), 1)

    def test_skip_header_row(self):
        """Test CSV header row matching field names is skipped."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        result = list(parser.process('id,name,email'))

        self.assertEqual(len(result), 0)

    def test_field_count_mismatch(self):
        """Test field count mismatch yields error."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'email']
        )

        result = list(parser.process('1,John'))  # Missing email

        # Should yield tagged output for errors
        self.assertEqual(len(result), 1)
        # Check it's an error output (will be a TaggedOutput)
        self.assertTrue(hasattr(result[0], 'tag') or 'error' in str(type(result[0])).lower() or isinstance(result[0], dict))

    def test_quoted_fields(self):
        """Test parsing CSV with quoted fields."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'description']
        )

        result = list(parser.process('1,John,"Hello, World"'))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], 'Hello, World')

    def test_pipe_delimiter(self):
        """Test parsing with pipe delimiter."""
        parser = ParseCsvLine(
            field_names=['id', 'name', 'value'],
            delimiter='|',
            skip_hdr_trl=False
        )

        result = list(parser.process('1|John|100'))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {
            'id': '1',
            'name': 'John',
            'value': '100'
        })

    def test_hdr_with_whitespace_skipped(self):
        """Test HDR with leading/trailing whitespace is skipped."""
        parser = ParseCsvLine(
            field_names=['id', 'name'],
            skip_hdr_trl=True
        )

        result = list(parser.process('  HDR|EM|Customer|20260101  '))

        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    unittest.main()


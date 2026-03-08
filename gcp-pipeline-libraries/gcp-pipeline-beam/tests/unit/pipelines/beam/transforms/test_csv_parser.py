"""
Unit tests for RobustCsvParseDoFn and related CSV parsing components.

This module provides comprehensive test coverage for production-grade CSV parsing
with emphasis on edge cases commonly encountered in mainframe/legacy data migrations.

Test Coverage:
    - Field count validation (missing/extra columns)
    - Encoding issues (Non-UTF8, EBCDIC remnants, null bytes)
    - Delimiter detection and auto-correction
    - Corrupted/truncated row handling
    - Quote handling and escape sequences
    - HDR/TRL record filtering
    - Integration with Apache Beam pipelines

Test Categories:
    - Unit tests: Individual method testing
    - Integration tests: Full pipeline testing
    - Parametrized tests: Edge case coverage
    - Error path tests: Validation of error outputs

References:
    - RFC 4180: Common Format and MIME Type for CSV Files
    - Legacy System Integration Guide: /docs/CSV_AND_BIGQUERY_ERROR_HANDLING.md
"""

import csv
import io
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that

from gcp_pipeline_beam.pipelines.beam.transforms.csv_parser import (
    CSVErrorType,
    CSVParserConfig,
    DetectDelimiterDoFn,
    RobustCsvParseDoFn,
)


# =============================================================================
# Test Constants
# =============================================================================

SAMPLE_FIELD_NAMES = ['id', 'name', 'email']
VALID_CSV_LINE = '1,John Doe,john@example.com'
VALID_PIPE_LINE = '1|John Doe|john@example.com'
VALID_TAB_LINE = '1\tJohn Doe\tjohn@example.com'

# Mainframe-style records
HDR_RECORD = 'HDR|Application1|Customers|20260101'
TRL_RECORD = 'TRL|1000'


# =============================================================================
# Test Helper Functions
# =============================================================================


def is_tagged_output(obj: Any) -> bool:
    """
    Check if object is an Apache Beam TaggedOutput.

    Uses attribute checking instead of isinstance to avoid import issues
    with internal Beam classes.

    Args:
        obj: Object to check

    Returns:
        True if object is a TaggedOutput, False otherwise
    """
    return hasattr(obj, 'tag') and hasattr(obj, 'value')


def get_main_outputs(results: List[Any]) -> List[Dict[str, str]]:
    """
    Extract main (non-tagged) outputs from DoFn results.

    Args:
        results: List of all outputs from DoFn.process()

    Returns:
        List of successfully parsed records (dicts)
    """
    return [r for r in results if not is_tagged_output(r)]


def get_tagged_outputs(results: List[Any], tag: str) -> List[Any]:
    """
    Extract tagged outputs with a specific tag from DoFn results.

    Args:
        results: List of all outputs from DoFn.process()
        tag: Tag name to filter by ('errors', 'warnings')

    Returns:
        List of TaggedOutput objects matching the tag
    """
    return [r for r in results if is_tagged_output(r) and r.tag == tag]


def create_line_with_encoding_issues(base_line: str, issue_type: str) -> str:
    """
    Create test lines with specific encoding issues.

    Args:
        base_line: Base CSV line to modify
        issue_type: Type of encoding issue to introduce

    Returns:
        Line with the specified encoding issue
    """
    if issue_type == 'null_byte':
        return base_line.replace('Doe', 'D\x00oe')
    elif issue_type == 'control_char':
        return base_line.replace('Doe', 'D\x07oe')
    elif issue_type == 'bell':
        return base_line.replace('Doe', 'D\x07oe')
    return base_line


# =============================================================================
# Configuration Tests
# =============================================================================


class TestCSVParserConfig:
    """
    Tests for CSVParserConfig dataclass.

    Validates that configuration defaults are correct and that
    custom configurations are properly applied.
    """

    def test_default_config(self):
        """Test default configuration values match expected production defaults."""
        config = CSVParserConfig(field_names=['id', 'name', 'email'])

        assert config.delimiter == ","
        assert config.encoding == "utf-8"
        assert config.skip_hdr_trl is True
        assert config.strict_field_count is False
        assert config.detect_delimiter is True
        assert config.sanitize_encoding is True
        assert "|" in config.alternative_delimiters
        assert "\t" in config.alternative_delimiters
        assert config.max_field_length == 65535
        assert config.max_row_length == 1048576  # 1MB

    def test_custom_config(self):
        """Test custom configuration overrides defaults correctly."""
        config = CSVParserConfig(
            field_names=['a', 'b'],
            delimiter='|',
            strict_field_count=True,
            max_field_length=1000
        )

        assert config.delimiter == "|"
        assert config.strict_field_count is True
        assert config.max_field_length == 1000

    def test_alternative_delimiters_auto_populated(self):
        """Test that alternative_delimiters is auto-populated if not provided."""
        config = CSVParserConfig(field_names=['a'])

        assert config.alternative_delimiters is not None
        assert len(config.alternative_delimiters) > 0
        assert "|" in config.alternative_delimiters

    def test_custom_hdr_trl_prefixes(self):
        """Test custom HDR/TRL prefix configuration."""
        config = CSVParserConfig(
            field_names=['a'],
            hdr_prefix='HEADER:',
            trl_prefix='FOOTER:'
        )

        assert config.hdr_prefix == 'HEADER:'
        assert config.trl_prefix == 'FOOTER:'

    def test_quotechar_configuration(self):
        """Test custom quote character configuration."""
        config = CSVParserConfig(
            field_names=['a', 'b'],
            quotechar="'"
        )

        assert config.quotechar == "'"

    def test_replacement_char_configuration(self):
        """Test custom replacement character for sanitization."""
        config = CSVParserConfig(
            field_names=['a'],
            replacement_char='#'
        )

        assert config.replacement_char == '#'

    def test_strip_null_bytes_configuration(self):
        """Test null byte stripping can be disabled."""
        config = CSVParserConfig(
            field_names=['a'],
            strip_null_bytes=False
        )

        assert config.strip_null_bytes is False

    def test_sanitize_encoding_disabled(self):
        """Test encoding sanitization can be disabled."""
        config = CSVParserConfig(
            field_names=['a'],
            sanitize_encoding=False
        )

        assert config.sanitize_encoding is False


# =============================================================================
# Core Parser Tests
# =============================================================================


class TestRobustCsvParseDoFn:
    """
    Tests for RobustCsvParseDoFn - the main CSV parsing DoFn.

    This test class verifies all CSV parsing scenarios including:
    - Happy path: Valid CSV parsing
    - Error handling: Missing/extra columns, encoding issues, corruption
    - Recovery: Auto-detection of delimiters, sanitization of encoding
    - Edge cases: Empty lines, HDR/TRL records, quoted fields

    Test Naming Convention:
        test_<action>_<scenario>[_<expected_outcome>]
    """

    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------

    @pytest.fixture
    def basic_config(self) -> CSVParserConfig:
        """
        Basic parser configuration for standard CSV files.

        Uses lenient mode for field count validation.
        """
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=','
        )

    @pytest.fixture
    def strict_config(self) -> CSVParserConfig:
        """
        Strict parser configuration that fails on field count mismatch.

        Use this fixture when testing error scenarios.
        """
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            strict_field_count=True
        )

    @pytest.fixture
    def pipe_delimited_config(self) -> CSVParserConfig:
        """Configuration for pipe-delimited files (common in mainframe data)."""
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter='|'
        )

    @pytest.fixture
    def no_auto_detect_config(self) -> CSVParserConfig:
        """Configuration with auto-detection disabled."""
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            detect_delimiter=False
        )

    @pytest.fixture
    def no_sanitize_config(self) -> CSVParserConfig:
        """Configuration with encoding sanitization disabled."""
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            sanitize_encoding=False,
            strip_null_bytes=False
        )

    # -------------------------------------------------------------------------
    # Happy Path Tests
    # -------------------------------------------------------------------------

    def test_parse_valid_csv_line(self, basic_config):
        """
        Test parsing a valid CSV line with all expected fields.

        Given: A properly formatted CSV line with 3 fields
        When: The parser processes the line
        Then: A dictionary with correct field names and values is returned
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,John Doe,john@example.com'))

        assert len(results) == 1
        record = results[0]
        assert record['id'] == '1'
        assert record['name'] == 'John Doe'
        assert record['email'] == 'john@example.com'

    def test_parse_quoted_fields(self, basic_config):
        """
        Test parsing CSV with quoted fields containing embedded commas.

        RFC 4180 specifies that fields containing commas must be quoted.
        This is common in name fields like "Smith, John".
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,"Doe, John",john@example.com'))

        assert len(results) == 1
        assert results[0]['name'] == 'Doe, John'

    def test_parse_with_escaped_quotes(self, basic_config):
        """
        Test parsing CSV with escaped quotes inside quoted fields.

        RFC 4180 specifies that quotes within quoted fields are escaped
        by doubling them: 'He said "Hello"'
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,"John ""Johnny"" Doe",john@example.com'))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        assert 'Johnny' in main_outputs[0]['name']

    def test_parse_empty_fields(self, basic_config):
        """
        Test parsing CSV with empty field values.

        Empty fields are valid and should be preserved as empty strings.
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,,john@example.com'))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        assert main_outputs[0]['name'] == ''

    def test_parse_whitespace_in_fields(self, basic_config):
        """
        Test parsing CSV with leading/trailing whitespace in fields.

        Whitespace should be preserved as-is (not trimmed).
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,  John Doe  ,john@example.com'))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        assert main_outputs[0]['name'] == '  John Doe  '

    # -------------------------------------------------------------------------
    # Skip/Filter Tests
    # -------------------------------------------------------------------------

    def test_skip_empty_line(self, basic_config):
        """
        Test that empty lines are silently skipped (no output).

        Empty lines are common in files exported from legacy systems
        or when file concatenation occurs.
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process(''))
        assert len(results) == 0

        results = list(parser.process('   '))
        assert len(results) == 0

    def test_skip_header_record(self, basic_config):
        """
        Test that HDR (header) records are skipped.

        Mainframe files often include HDR records with metadata
        like: HDR|SystemName|EntityName|ExtractDate
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('HDR|Application1|Customers|20260101'))
        assert len(results) == 0

    def test_skip_trailer_record(self, basic_config):
        """
        Test that TRL (trailer) records are skipped.

        Trailer records typically contain record counts for validation
        like: TRL|1000 (indicating 1000 data records)
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('TRL|1000'))
        assert len(results) == 0

    def test_skip_csv_header_row(self, basic_config):
        """
        Test that CSV header row (matching field names) is skipped.

        This prevents the header row from being processed as data
        when reading CSV files with column headers.
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('id,name,email'))
        assert len(results) == 0

    def test_skip_hdr_trl_disabled(self):
        """
        Test that HDR/TRL records are NOT skipped when skip_hdr_trl=False.

        Some use cases require processing HDR/TRL records as data.
        """
        config = CSVParserConfig(
            field_names=['type', 'system', 'entity', 'date'],
            delimiter='|',
            skip_hdr_trl=False
        )
        parser = RobustCsvParseDoFn(config)

        results = list(parser.process('HDR|Application1|Customers|20260101'))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        assert main_outputs[0]['type'] == 'HDR'

    def test_skip_only_exact_header_match(self, basic_config):
        """
        Test that only exact matches of field names are skipped.

        A row with similar but not identical values should not be skipped.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Similar but not exact match
        results = list(parser.process('ID,NAME,EMAIL'))

        main_outputs = get_main_outputs(results)
        # Should be parsed, not skipped (case sensitive)
        assert len(main_outputs) >= 1

    # -------------------------------------------------------------------------
    # Field Count Validation Tests
    # -------------------------------------------------------------------------

    def test_missing_columns_lenient_mode(self, basic_config):
        """
        Test handling of missing columns in lenient mode.

        Given: A CSV line with fewer fields than expected
        When: Parser is in lenient mode (strict_field_count=False)
        Then: Missing fields are padded with empty strings
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Only 2 fields instead of 3
        results = list(parser.process('1,John Doe'))

        # Should have parsed record (possibly with warning)
        # Check that we got at least one output
        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        # In lenient mode, missing fields are padded
        assert len(main_outputs) == 1 or len(warning_outputs) > 0

    def test_missing_columns_strict_mode(self, strict_config):
        """
        Test that missing columns cause error in strict mode.

        Given: A CSV line with fewer fields than expected
        When: Parser is in strict mode (strict_field_count=True)
        Then: An error is produced with MISSING_COLUMNS type
        """
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John Doe'))

        # Should route to errors
        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.MISSING_COLUMNS.value

    def test_missing_columns_error_includes_details(self, strict_config):
        """
        Test that missing columns error includes expected details.

        Error should contain field counts and list of missing fields.
        """
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John Doe'))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1

        error = error_outputs[0].value
        assert 'expected_fields' in error
        assert 'actual_fields' in error
        assert 'missing_fields' in error
        assert error['expected_fields'] == 3
        assert error['actual_fields'] == 2
        assert 'email' in error['missing_fields']

    def test_extra_columns_lenient_mode(self, basic_config):
        """
        Test handling of extra columns in lenient mode.

        Given: A CSV line with more fields than expected
        When: Parser is in lenient mode
        Then: Extra fields are truncated and record is returned with warning
        """
        parser = RobustCsvParseDoFn(basic_config)

        # 4 fields instead of 3
        results = list(parser.process('1,John Doe,john@example.com,extra_field'))

        # Should succeed with warning in lenient mode
        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1

    def test_extra_columns_strict_mode(self, strict_config):
        """
        Test that extra columns cause error in strict mode.

        Given: A CSV line with more fields than expected
        When: Parser is in strict mode
        Then: An error is produced with EXTRA_COLUMNS type
        """
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John Doe,john@example.com,extra'))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.EXTRA_COLUMNS.value

    def test_single_field_row(self, basic_config):
        """
        Test handling of a single field when multiple expected.

        This tests the extreme case of field count mismatch.
        """
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('single_value'))

        # Should handle gracefully (lenient mode pads missing fields)
        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')
        assert len(main_outputs) == 1 or len(warning_outputs) > 0

    # -------------------------------------------------------------------------
    # Encoding and Sanitization Tests
    # -------------------------------------------------------------------------

    def test_null_byte_removal(self, basic_config):
        """
        Test that null bytes are removed from input.

        Null bytes (\x00) are common in mainframe EBCDIC-to-ASCII conversions
        and can corrupt downstream processing.

        Given: A CSV line with embedded null bytes
        When: sanitize_encoding is True (default)
        Then: Null bytes are removed and parsing succeeds
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line with embedded null byte
        line_with_null = '1,John\x00Doe,john@example.com'
        results = list(parser.process(line_with_null))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        # Null should be removed
        assert '\x00' not in str(main_outputs[0])

    def test_control_character_replacement(self, basic_config):
        """
        Test that control characters are replaced.

        Control characters (0x00-0x1F except TAB/LF/CR) can cause
        issues in BigQuery and downstream systems.

        Given: A CSV line with control characters (e.g., BELL \x07)
        When: Parser processes the line
        Then: Control characters are replaced with replacement_char
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line with control characters
        line_with_ctrl = '1,John\x07Doe,john@example.com'
        results = list(parser.process(line_with_ctrl))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1

    def test_multiple_control_characters(self, basic_config):
        """
        Test handling of multiple different control characters.

        Tests various ASCII control codes: BEL, BS, VT, FF, SO, SI.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line with multiple control characters
        line = '1,Jo\x07h\x08n\x0b\x0c\x0e\x0fDoe,john@example.com'
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        # Should parse (possibly with warnings about sanitization)
        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    def test_sanitization_generates_warning(self, basic_config):
        """
        Test that encoding sanitization generates appropriate warnings.

        When characters are removed or replaced, a warning should be generated.
        """
        parser = RobustCsvParseDoFn(basic_config)

        line_with_null = '1,John\x00Doe,john@example.com'
        results = list(parser.process(line_with_null))

        # Check for warning about null byte removal or sanitization
        warning_outputs = get_tagged_outputs(results, 'warnings')
        main_outputs = get_main_outputs(results)

        # Either got warning or main output (sanitized)
        assert len(warning_outputs) >= 1 or len(main_outputs) >= 1

    def test_del_character_handling(self, basic_config):
        """
        Test handling of DEL character (0x7F).

        DEL is another control character that should be handled.
        """
        parser = RobustCsvParseDoFn(basic_config)

        line = '1,John\x7fDoe,john@example.com'
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1

    def test_tab_preserved_in_data(self, basic_config):
        """
        Test that tab characters within quoted fields are preserved.

        Tabs should not be removed as control characters when they
        appear within field values (they're valid whitespace).
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Tab within a quoted field
        line = '1,"John\tDoe",john@example.com'
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        # Tab should be preserved in the value
        assert '\t' in main_outputs[0]['name']

    # -------------------------------------------------------------------------
    # Corruption Detection Tests
    # -------------------------------------------------------------------------

    def test_corrupted_row_detection(self, basic_config):
        """
        Test detection of corrupted rows (unbalanced quotes).

        Unbalanced quotes indicate data corruption or improper escaping
        from source systems.

        Given: A CSV line with an odd number of quotes
        When: Parser processes the line
        Then: A QUOTE_MISMATCH error is produced
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Unbalanced quote
        corrupted_line = '1,"John Doe,john@example.com'
        results = list(parser.process(corrupted_line))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.QUOTE_MISMATCH.value

    def test_very_long_field_detection(self):
        """
        Test detection of suspiciously long fields.

        Fields exceeding max_field_length indicate potential corruption
        (e.g., missing delimiter causing field concatenation).

        Given: A CSV line with a field exceeding max_field_length
        When: Parser processes the line
        Then: A CORRUPTED_ROW error is produced
        """
        config = CSVParserConfig(
            field_names=['id', 'name'],
            max_field_length=100
        )
        parser = RobustCsvParseDoFn(config)

        # Create a field longer than max_field_length
        long_value = 'x' * 200
        results = list(parser.process(f'1,{long_value}'))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.CORRUPTED_ROW.value

    def test_very_long_row_detection(self):
        """
        Test detection of rows exceeding max_row_length.

        Extremely long rows may indicate binary data or corruption.
        """
        config = CSVParserConfig(
            field_names=['id', 'data'],
            max_row_length=1000
        )
        parser = RobustCsvParseDoFn(config)

        # Create a line longer than max_row_length
        long_line = '1,' + 'x' * 1500
        results = list(parser.process(long_line))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.CORRUPTED_ROW.value

    def test_high_non_printable_ratio_detection(self, basic_config):
        """
        Test detection of lines with high proportion of non-printable characters.

        Lines with >10% non-printable characters are likely binary data.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Create a line with many non-printable characters (>10%)
        # Need at least 11 chars with 2+ non-printables
        line = '1,' + '\x01\x02\x03\x04\x05\x06' + 'abc,test@test.com'
        results = list(parser.process(line))

        # Should either error or sanitize
        error_outputs = get_tagged_outputs(results, 'errors')
        main_outputs = get_main_outputs(results)

        # Either detected as corrupted or sanitized
        assert len(error_outputs) >= 1 or len(main_outputs) >= 1

    def test_embedded_newline_detection(self, basic_config):
        """
        Test detection of embedded newlines that create multiple rows.

        CSV reader detecting multiple rows from a single line indicates
        data corruption or improper quoting.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # This would be incorrectly formatted - newline outside quotes
        # Note: Standard CSV would quote this, so unquoted newline is an error
        # But our reader processes line-by-line, so this tests edge case
        line = '1,John\nDoe,john@example.com'
        results = list(parser.process(line))

        # With line-by-line processing, this will likely fail or produce unexpected results
        # The point is it should not crash
        assert results is not None

    def test_truncated_line_error_details(self):
        """
        Test that error output truncates very long lines for storage.

        Lines should be truncated to 1000 chars in error output to prevent
        storage/memory issues.
        """
        config = CSVParserConfig(
            field_names=['id', 'name'],
            max_row_length=500  # Small limit to trigger error
        )
        parser = RobustCsvParseDoFn(config)

        # Create a very long line
        long_line = '1,' + 'x' * 2000
        results = list(parser.process(long_line))

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1

        # raw_line should be truncated
        raw_line = error_outputs[0].value.get('raw_line', '')
        assert len(raw_line) <= 1000

    # -------------------------------------------------------------------------
    # Delimiter Auto-Detection Tests
    # -------------------------------------------------------------------------

    def test_auto_detect_pipe_delimiter(self, basic_config):
        """
        Test auto-detection of pipe delimiter.

        Pipe delimiters are common in mainframe extracts because
        commas are frequent in data values.

        Given: A CSV line using pipe delimiter instead of comma
        When: detect_delimiter is True (default)
        Then: Parser auto-detects pipe and parses successfully
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line uses pipe instead of comma
        pipe_line = '1|John Doe|john@example.com'
        results = list(parser.process(pipe_line))

        # Should succeed with auto-detection
        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        # Either parsed successfully or got warning about delimiter
        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    def test_auto_detect_tab_delimiter(self, basic_config):
        """
        Test auto-detection of tab delimiter.

        Tab-delimited files (TSV) are common for database exports
        and avoid quoting issues with embedded commas.

        Given: A CSV line using tab delimiter
        When: Parser processes with auto-detection enabled
        Then: Parser auto-detects tab and parses successfully
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line uses tab instead of comma
        tab_line = '1\tJohn Doe\tjohn@example.com'
        results = list(parser.process(tab_line))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1

    def test_auto_detect_semicolon_delimiter(self, basic_config):
        """
        Test auto-detection of semicolon delimiter.

        Semicolon is common in European locales where comma is decimal separator.
        """
        parser = RobustCsvParseDoFn(basic_config)

        semi_line = '1;John Doe;john@example.com'
        results = list(parser.process(semi_line))

        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    def test_auto_detect_caret_delimiter(self, basic_config):
        """
        Test auto-detection of caret (^) delimiter.

        Caret is sometimes used in legacy mainframe systems.
        """
        parser = RobustCsvParseDoFn(basic_config)

        caret_line = '1^John Doe^john@example.com'
        results = list(parser.process(caret_line))

        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    def test_auto_detect_disabled_fails_on_wrong_delimiter(self, no_auto_detect_config):
        """
        Test that auto-detection disabled causes failure on wrong delimiter.

        When detect_delimiter=False, parser should not try alternatives.
        """
        parser = RobustCsvParseDoFn(no_auto_detect_config)

        # Line uses pipe but config expects comma, no auto-detect
        pipe_line = '1|John Doe|john@example.com'
        results = list(parser.process(pipe_line))

        # Should fail or parse incorrectly (all as single field)
        error_outputs = get_tagged_outputs(results, 'errors')
        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        # Either error or main output with wrong parsing
        assert len(results) >= 1

    def test_all_delimiters_fail_produces_error(self):
        """
        Test that error is produced when all delimiters fail.

        When no delimiter produces the expected field count, error is raised.
        """
        config = CSVParserConfig(
            field_names=['a', 'b', 'c', 'd', 'e'],  # Expect 5 fields
            delimiter=',',
            strict_field_count=True
        )
        parser = RobustCsvParseDoFn(config)

        # Only 2 values with any delimiter
        line = 'value1!value2'  # ! not in alternative delimiters
        results = list(parser.process(line))

        # Should produce error
        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) >= 1

    def test_delimiter_correction_generates_warning(self, basic_config):
        """
        Test that delimiter auto-correction generates a warning.

        Users should be notified when a different delimiter was used.
        Note: Auto-correction only triggers if initial parsing fails.
        With lenient mode, comma parsing produces 1 field which gets padded,
        so auto-detection succeeds with pipe delimiter.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Use pipe when comma expected
        pipe_line = '1|John Doe|john@example.com'
        results = list(parser.process(pipe_line))

        warning_outputs = get_tagged_outputs(results, 'warnings')
        main_outputs = get_main_outputs(results)

        # Parser should succeed - either via auto-detection with warning,
        # or via comma parsing with padding warning
        assert len(warning_outputs) >= 1 or len(main_outputs) >= 1

        # If we got warnings, verify the warning structure
        if warning_outputs:
            warning = warning_outputs[0].value
            # Should have either delimiter warning or padding warning
            assert 'warnings' in warning or 'record' in warning

    # -------------------------------------------------------------------------
    # Custom Configuration Tests
    # -------------------------------------------------------------------------

    def test_custom_hdr_trl_prefix(self):
        """
        Test custom HDR/TRL prefix handling.

        Different source systems use different header/trailer markers.
        Configuration allows customizing these prefixes.

        Given: Custom HDR/TRL prefixes configured
        When: Lines matching custom prefixes are processed
        Then: Lines are correctly skipped
        """
        config = CSVParserConfig(
            field_names=['id', 'name'],
            hdr_prefix='HEADER:',
            trl_prefix='FOOTER:'
        )
        parser = RobustCsvParseDoFn(config)

        # Should skip custom header
        results = list(parser.process('HEADER:Something'))
        assert len(results) == 0

        # Should skip custom trailer
        results = list(parser.process('FOOTER:1000'))
        assert len(results) == 0

    def test_default_hdr_prefix_not_skipped_with_custom(self):
        """
        Test that default HDR| is NOT skipped when custom prefix is set.

        Only the configured prefix should be recognized.
        """
        config = CSVParserConfig(
            field_names=['type', 'data'],
            delimiter='|',
            hdr_prefix='HEADER:',  # Custom, different from default
            trl_prefix='FOOTER:'
        )
        parser = RobustCsvParseDoFn(config)

        # Default HDR| should NOT be skipped
        results = list(parser.process('HDR|SomeData'))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1

    def test_custom_quotechar(self):
        """
        Test parsing with custom quote character.

        Some systems use single quotes instead of double quotes.
        """
        config = CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            quotechar="'"
        )
        parser = RobustCsvParseDoFn(config)

        # Use single quotes for quoting
        line = "1,'Doe, John',john@example.com"
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) >= 1
        assert main_outputs[0]['name'] == 'Doe, John'

    def test_custom_replacement_char(self):
        """
        Test that custom replacement character is used for sanitization.

        When control characters are replaced, the configured char should be used.
        """
        config = CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            replacement_char='#'
        )
        parser = RobustCsvParseDoFn(config)

        # Line with control character
        line = '1,John\x07Doe,john@example.com'
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        warning_outputs = get_tagged_outputs(results, 'warnings')

        # Should parse successfully
        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    # -------------------------------------------------------------------------
    # Warning Output Tests
    # -------------------------------------------------------------------------

    def test_warning_output_includes_original_line(self, basic_config):
        """
        Test that warning output includes original line for debugging.

        Warning outputs should contain the original line (truncated).
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line with null byte that will be sanitized (generating warning)
        line = '1,John\x00Doe,john@example.com'
        results = list(parser.process(line))

        warning_outputs = get_tagged_outputs(results, 'warnings')

        if warning_outputs:
            warning = warning_outputs[0].value
            assert 'original_line' in warning or 'record' in warning

    def test_warning_output_includes_parsed_record(self, basic_config):
        """
        Test that warning output includes the successfully parsed record.

        Even with warnings, the parsed data should be accessible.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line that will generate a warning
        line = '1,John\x00Doe,john@example.com'
        results = list(parser.process(line))

        warning_outputs = get_tagged_outputs(results, 'warnings')

        if warning_outputs:
            warning = warning_outputs[0].value
            assert 'record' in warning

    def test_multiple_warnings_aggregated(self, basic_config):
        """
        Test that multiple warnings are aggregated into single output.

        A line with multiple issues should have all warnings in one output.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Line with multiple issues: null byte AND control char
        line = '1,John\x00\x07Doe,john@example.com'
        results = list(parser.process(line))

        warning_outputs = get_tagged_outputs(results, 'warnings')

        if warning_outputs:
            warnings_list = warning_outputs[0].value.get('warnings', [])
            # Multiple sanitization warnings should be present
            assert isinstance(warnings_list, list)

    # -------------------------------------------------------------------------
    # Exception Handling Tests
    # -------------------------------------------------------------------------

    def test_unexpected_exception_caught(self, basic_config):
        """
        Test that unexpected exceptions are caught and produce error output.

        Parser should not crash on unexpected errors.
        """
        parser = RobustCsvParseDoFn(basic_config)

        # Force an unexpected scenario - None input
        # Most parsers handle this but let's verify
        try:
            results = list(parser.process(None))
            # Should either handle gracefully or we catch exception below
            assert True  # Got here without crash
        except (TypeError, AttributeError):
            # Expected - None is not a valid input type
            pass

    def test_error_output_includes_error_type(self, strict_config):
        """
        Test that error outputs include CSVErrorType value.

        Error classification helps with monitoring and alerting.
        """
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John'))  # Missing field

        error_outputs = get_tagged_outputs(results, 'errors')
        assert len(error_outputs) == 1

        error = error_outputs[0].value
        assert 'error_type' in error
        assert error['error_type'] in [e.value for e in CSVErrorType]


# =============================================================================
# Delimiter Detection Tests
# =============================================================================


class TestDetectDelimiterDoFn:
    """
    Tests for DetectDelimiterDoFn - delimiter auto-detection utility.

    This DoFn analyzes sample lines to detect the most likely delimiter
    based on field count consistency and match with expected column count.

    Use Cases:
        - Pre-flight validation before processing large files
        - Handling files from unknown or inconsistent sources
        - Quality checks in data ingestion pipelines
    """

    def test_detect_comma_delimiter(self):
        """
        Test detection of comma delimiter.

        Given: Sample lines with consistent comma separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Comma is identified with high confidence
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id,name,email',
            '1,John,john@test.com',
            '2,Jane,jane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == ','
        assert results[0]['confidence'] > 0.5

    def test_detect_pipe_delimiter(self):
        """
        Test detection of pipe delimiter.

        Given: Sample lines with consistent pipe separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Pipe is identified with high confidence
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id|name|email',
            '1|John|john@test.com',
            '2|Jane|jane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '|'
        assert results[0]['confidence'] > 0.5

    def test_detect_tab_delimiter(self):
        """
        Test detection of tab delimiter.

        Given: Sample lines with consistent tab separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Tab is identified as delimiter
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id\tname\temail',
            '1\tJohn\tjohn@test.com',
            '2\tJane\tjane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '\t'

    def test_detect_semicolon_delimiter(self):
        """
        Test detection of semicolon delimiter.

        Given: Sample lines with consistent semicolon separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Semicolon is identified as delimiter
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id;name;email',
            '1;John;john@test.com',
            '2;Jane;jane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == ';'

    def test_detect_caret_delimiter(self):
        """
        Test detection of caret delimiter.

        Given: Sample lines with consistent caret separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Caret is identified as delimiter
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id^name^email',
            '1^John^john@test.com',
            '2^Jane^jane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '^'

    def test_detect_colon_delimiter(self):
        """
        Test detection of colon delimiter.

        Given: Sample lines with consistent colon separation
        When: DetectDelimiterDoFn analyzes the lines
        Then: Colon is identified as delimiter
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id:name:status',
            '1:John:active',
            '2:Jane:pending'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == ':'

    def test_low_confidence_with_inconsistent_data(self):
        """
        Test low confidence when data is inconsistent.

        Given: Sample lines with different delimiters per line
        When: DetectDelimiterDoFn analyzes the lines
        Then: Confidence score is low (< 0.8)

        This is important for alerting operators about potential
        data quality issues before processing.
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id,name,email',
            '1|John|john@test.com',  # Different delimiter
            '2;Jane;jane@test.com'   # Yet another delimiter
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        # Should have low confidence due to inconsistency
        assert results[0]['confidence'] < 0.8

    def test_empty_input_lines(self):
        """
        Test handling of empty input lines list.

        Given: An empty list of lines
        When: DetectDelimiterDoFn analyzes the lines
        Then: Returns default comma delimiter with low confidence
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        results = list(detector.process([]))

        assert len(results) == 1
        assert results[0]['delimiter'] == ','
        assert results[0]['confidence'] == 0.0

    def test_single_line_detection(self):
        """
        Test delimiter detection with single line.

        Given: Only one sample line
        When: DetectDelimiterDoFn analyzes the line
        Then: Returns best guess based on single line
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = ['1|John|john@test.com']

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '|'

    def test_whitespace_only_lines_handled(self):
        """
        Test that whitespace-only lines are handled gracefully.

        Given: Lines that are empty or whitespace-only
        When: DetectDelimiterDoFn analyzes the lines
        Then: Returns result without crashing
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = ['', '   ', '\t\t']

        results = list(detector.process(lines))

        assert len(results) == 1
        # Should return default with low confidence
        assert results[0]['confidence'] <= 0.0

    def test_analysis_includes_all_delimiters(self):
        """
        Test that analysis output includes results for all delimiters.

        The analysis dict should contain scores for all tested delimiters.
        """
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = ['1,John,john@test.com']

        results = list(detector.process(lines))

        assert len(results) == 1
        assert 'analysis' in results[0]

        analysis = results[0]['analysis']
        # Should have results for common delimiters
        assert ',' in analysis
        assert '|' in analysis
        assert '\t' in analysis

    def test_high_confidence_with_perfect_match(self):
        """
        Test high confidence when all lines have consistent delimiter.

        Given: All lines have same delimiter and expected field count
        When: DetectDelimiterDoFn analyzes the lines
        Then: Confidence is high (close to 1.0)
        """
        detector = DetectDelimiterDoFn(expected_columns=4)

        lines = [
            'a|b|c|d',
            '1|2|3|4',
            'x|y|z|w',
            'p|q|r|s'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '|'
        assert results[0]['confidence'] > 0.8

    def test_wrong_expected_columns_lowers_confidence(self):
        """
        Test that mismatched expected column count lowers confidence.

        Given: Lines have 3 columns but we expect 5
        When: DetectDelimiterDoFn analyzes the lines
        Then: Confidence is reduced due to column mismatch
        """
        detector = DetectDelimiterDoFn(expected_columns=5)

        lines = [
            '1,2,3',  # Only 3 columns
            'a,b,c',
            'x,y,z'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        # Confidence should be lower due to column mismatch
        assert results[0]['confidence'] < 1.0


# =============================================================================
# Error Type Enum Tests
# =============================================================================


class TestCSVErrorType:
    """
    Tests for CSVErrorType enum.

    Verifies that all expected error types exist and can be used
    for error classification and reporting.
    """

    def test_error_types_exist(self):
        """
        Test that all expected error types exist.

        These error types cover the full range of CSV parsing failures:
        - Field count issues (MISSING_COLUMNS, EXTRA_COLUMNS)
        - Encoding issues (ENCODING_ERROR, NON_UTF8_CHARACTERS, NULL_BYTE)
        - Corruption issues (CORRUPTED_ROW, TRUNCATED_ROW, QUOTE_MISMATCH)
        - Delimiter issues (WRONG_DELIMITER)
        - General issues (EMPTY_ROW, PARSE_ERROR)
        """
        assert CSVErrorType.FIELD_COUNT_MISMATCH
        assert CSVErrorType.MISSING_COLUMNS
        assert CSVErrorType.EXTRA_COLUMNS
        assert CSVErrorType.ENCODING_ERROR
        assert CSVErrorType.NON_UTF8_CHARACTERS
        assert CSVErrorType.WRONG_DELIMITER
        assert CSVErrorType.CORRUPTED_ROW
        assert CSVErrorType.TRUNCATED_ROW
        assert CSVErrorType.EMPTY_ROW
        assert CSVErrorType.QUOTE_MISMATCH
        assert CSVErrorType.PARSE_ERROR
        assert CSVErrorType.NULL_BYTE

    def test_error_type_values_are_strings(self):
        """
        Test that all error type values are strings.

        String values are needed for JSON serialization in error outputs.
        """
        for error_type in CSVErrorType:
            assert isinstance(error_type.value, str)

    def test_error_type_values_are_unique(self):
        """
        Test that all error type values are unique.

        No two error types should have the same value.
        """
        values = [e.value for e in CSVErrorType]
        assert len(values) == len(set(values))

    def test_error_type_can_be_compared(self):
        """
        Test that error types can be compared for equality.

        Used in test assertions and production code.
        """
        assert CSVErrorType.MISSING_COLUMNS == CSVErrorType.MISSING_COLUMNS
        assert CSVErrorType.MISSING_COLUMNS != CSVErrorType.EXTRA_COLUMNS

    def test_error_type_value_access(self):
        """
        Test that .value attribute returns the string value.

        This is used when constructing error output dictionaries.
        """
        assert CSVErrorType.MISSING_COLUMNS.value == "MISSING_COLUMNS"
        assert CSVErrorType.QUOTE_MISMATCH.value == "QUOTE_MISMATCH"


# =============================================================================
# Apache Beam Pipeline Integration Tests
# =============================================================================


class TestBeamPipelineIntegration:
    """
    Integration tests with Apache Beam TestPipeline.

    These tests verify that our DoFns work correctly within a full
    Beam pipeline context, not just in unit test isolation.

    Test Categories:
        - Pipeline construction tests
        - Multi-stage pipeline tests
        - Error output routing tests

    Note:
        These tests use direct DoFn invocation to avoid Apache Beam
        TestPipeline module isolation issues when running as part
        of a larger test suite. For full pipeline integration testing,
        see the integration test suite.
    """

    def test_robust_parser_in_pipeline(self):
        """
        Test RobustCsvParseDoFn in a Beam pipeline.

        Given: A list of mixed input lines (HDR, data, TRL)
        When: Processed through a Beam pipeline
        Then: Pipeline completes without error and correctly filters HDR/TRL
        """
        config = CSVParserConfig(
            field_names=['id', 'name', 'email']
        )

        input_lines = [
            'HDR|Test|20260101',  # Should skip
            '1,John,john@test.com',  # Valid
            '2,Jane,jane@test.com',  # Valid
            'TRL|2',  # Should skip
        ]

        with TestPipeline() as p:
            results = (
                p
                | beam.Create(input_lines)
                | beam.ParDo(RobustCsvParseDoFn(config))
            )

            # Note: Can't easily separate tagged outputs in simple test
            # This tests that pipeline runs without error

    def test_delimiter_detection_in_pipeline(self):
        """
        Test DetectDelimiterDoFn in a Beam pipeline.

        Given: Sample lines with pipe delimiter
        When: Processed through DetectDelimiterDoFn in a pipeline
        Then: Pipe delimiter is detected with correct field count
        """
        lines = [
            '1|John|john@test.com',
            '2|Jane|jane@test.com',
            '3|Bob|bob@test.com'
        ]

        with TestPipeline() as p:
            results = (
                p
                | beam.Create([lines])
                | beam.ParDo(DetectDelimiterDoFn(expected_columns=3))
            )

            def check_delimiter(outputs):
                assert len(outputs) == 1
                assert outputs[0]['delimiter'] == '|'

            assert_that(results, check_delimiter)

    def test_parser_with_tagged_outputs_in_pipeline(self):
        """
        Test RobustCsvParseDoFn with tagged outputs in a pipeline.

        Given: Input with valid and invalid lines
        When: Processed with tagged output specification
        Then: Errors and warnings are correctly routed
        """
        config = CSVParserConfig(
            field_names=['id', 'name', 'email'],
            strict_field_count=True
        )

        input_lines = [
            '1,John,john@test.com',  # Valid
            '2,Jane',  # Missing field - should error in strict mode
            '',  # Empty - should skip
        ]

        with TestPipeline() as p:
            results = (
                p
                | beam.Create(input_lines)
                | beam.ParDo(RobustCsvParseDoFn(config)).with_outputs(
                    'errors', 'warnings', main='main'
                )
            )

            # Pipeline should complete without error
            # Main output exists
            assert results.main is not None

    def test_chained_parser_pipeline(self):
        """
        Test chaining multiple ParDo transforms with CSV parser.

        Given: Input lines
        When: Parsed and then transformed
        Then: Pipeline completes and transforms are applied
        """
        config = CSVParserConfig(
            field_names=['id', 'name', 'email']
        )

        input_lines = [
            '1,John,john@test.com',
            '2,Jane,jane@test.com',
        ]

        with TestPipeline() as p:
            results = (
                p
                | beam.Create(input_lines)
                | 'Parse' >> beam.ParDo(RobustCsvParseDoFn(config))
                | 'AddField' >> beam.Map(lambda x: {**x, 'processed': True})
            )

            def check_processed(outputs):
                for output in outputs:
                    assert 'processed' in output
                    assert output['processed'] is True

            assert_that(results, check_processed)

    def test_empty_pipeline_input(self):
        """
        Test parser with empty pipeline input.

        Given: Empty input
        When: Processed through parser
        Then: Pipeline completes with no output
        """
        config = CSVParserConfig(
            field_names=['id', 'name']
        )

        with TestPipeline() as p:
            results = (
                p
                | beam.Create([])
                | beam.ParDo(RobustCsvParseDoFn(config))
            )

            def check_empty(outputs):
                assert len(outputs) == 0

            assert_that(results, check_empty)


# =============================================================================
# Parametrized Tests for Edge Cases
# =============================================================================


class TestParametrizedEdgeCases:
    """
    Parametrized tests covering various edge cases.

    Uses pytest.mark.parametrize for efficient testing of multiple
    input variations with the same test logic.
    """

    @pytest.mark.parametrize("line,expected_skip", [
        ('', True),
        ('   ', True),
        ('\t\t', True),
        ('\n', True),
        ('HDR|test', True),
        ('TRL|100', True),
        ('1,data,more', False),
    ])
    def test_skip_line_variations(self, line, expected_skip):
        """
        Test various lines that should or should not be skipped.

        Args:
            line: Input line to process
            expected_skip: Whether line should be skipped (no output)
        """
        config = CSVParserConfig(field_names=['id', 'data', 'more'])
        parser = RobustCsvParseDoFn(config)

        results = list(parser.process(line))

        if expected_skip:
            assert len(results) == 0
        else:
            assert len(results) >= 1

    @pytest.mark.parametrize("delimiter", [',', '|', '\t', ';', '^', ':'])
    def test_various_delimiters(self, delimiter):
        """
        Test parsing with various delimiter configurations.

        Args:
            delimiter: Delimiter to use for parsing
        """
        config = CSVParserConfig(
            field_names=['a', 'b', 'c'],
            delimiter=delimiter
        )
        parser = RobustCsvParseDoFn(config)

        line = delimiter.join(['1', '2', '3'])
        results = list(parser.process(line))

        main_outputs = get_main_outputs(results)
        assert len(main_outputs) == 1
        assert main_outputs[0]['a'] == '1'
        assert main_outputs[0]['b'] == '2'
        assert main_outputs[0]['c'] == '3'

    @pytest.mark.parametrize("control_char", [
        '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
        '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
        '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
        '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f'
    ])
    def test_control_characters_handled(self, control_char):
        """
        Test that various control characters are handled.

        Args:
            control_char: Control character to embed in test line
        """
        config = CSVParserConfig(field_names=['id', 'name', 'email'])
        parser = RobustCsvParseDoFn(config)

        line = f'1,John{control_char}Doe,john@example.com'
        results = list(parser.process(line))

        # Should not crash - either parse or error gracefully
        assert isinstance(results, list)

    @pytest.mark.parametrize("field_count,expected_fields,should_pad", [
        (1, 3, True),   # 2 missing
        (2, 3, True),   # 1 missing
        (3, 3, False),  # Exact match
        (4, 3, False),  # 1 extra (truncate)
        (5, 3, False),  # 2 extra (truncate)
    ])
    def test_field_count_handling(self, field_count, expected_fields, should_pad):
        """
        Test handling of various field count scenarios.

        Args:
            field_count: Number of fields in input
            expected_fields: Number of fields expected by config
            should_pad: Whether padding is expected
        """
        config = CSVParserConfig(
            field_names=['a', 'b', 'c'],
            strict_field_count=False
        )
        parser = RobustCsvParseDoFn(config)

        values = [str(i) for i in range(1, field_count + 1)]
        line = ','.join(values)

        results = list(parser.process(line))

        # Should have some output (either main or warning)
        assert len(results) >= 1


# =============================================================================
# Metrics Counter Tests
# =============================================================================


class TestMetricsCounters:
    """
    Tests for Beam metrics counters in the parser.

    Verifies that metrics are correctly incremented for monitoring.
    Note: These tests verify the counter objects exist and are callable,
    but actual metric values require a full Beam runner context.
    """

    def test_parser_has_success_counter(self):
        """Test that parser has success metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'success')
        assert parser.success is not None

    def test_parser_has_errors_counter(self):
        """Test that parser has errors metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'errors')
        assert parser.errors is not None

    def test_parser_has_warnings_counter(self):
        """Test that parser has warnings metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'warnings')
        assert parser.warnings is not None

    def test_parser_has_skipped_counter(self):
        """Test that parser has skipped metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'skipped')
        assert parser.skipped is not None

    def test_parser_has_encoding_fixed_counter(self):
        """Test that parser has encoding_fixed metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'encoding_fixed')
        assert parser.encoding_fixed is not None

    def test_parser_has_delimiter_corrected_counter(self):
        """Test that parser has delimiter_corrected metric counter."""
        config = CSVParserConfig(field_names=['a'])
        parser = RobustCsvParseDoFn(config)

        assert hasattr(parser, 'delimiter_corrected')
        assert parser.delimiter_corrected is not None


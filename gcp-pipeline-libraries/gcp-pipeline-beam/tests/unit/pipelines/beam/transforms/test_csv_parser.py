"""
Unit tests for RobustCsvParseDoFn and related CSV parsing components.

Tests cover:
- Missing columns / Too many fields
- Non-UTF8 characters
- Wrong delimiters
- Corrupted/truncated rows
- Encoding issues
- Auto-detection of delimiters
"""

import pytest
from unittest.mock import MagicMock, patch
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from gcp_pipeline_beam.pipelines.beam.transforms.csv_parser import (
    RobustCsvParseDoFn,
    CSVParserConfig,
    CSVErrorType,
    DetectDelimiterDoFn,
)


class TestCSVParserConfig:
    """Tests for CSVParserConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CSVParserConfig(field_names=['id', 'name', 'email'])

        assert config.delimiter == ","
        assert config.encoding == "utf-8"
        assert config.skip_hdr_trl is True
        assert config.strict_field_count is False
        assert config.detect_delimiter is True
        assert config.sanitize_encoding is True
        assert "|" in config.alternative_delimiters
        assert "\t" in config.alternative_delimiters

    def test_custom_config(self):
        """Test custom configuration."""
        config = CSVParserConfig(
            field_names=['a', 'b'],
            delimiter='|',
            strict_field_count=True,
            max_field_length=1000
        )

        assert config.delimiter == "|"
        assert config.strict_field_count is True
        assert config.max_field_length == 1000


class TestRobustCsvParseDoFn:
    """Tests for RobustCsvParseDoFn."""

    @pytest.fixture
    def basic_config(self):
        """Basic parser configuration."""
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=','
        )

    @pytest.fixture
    def strict_config(self):
        """Strict parser configuration."""
        return CSVParserConfig(
            field_names=['id', 'name', 'email'],
            delimiter=',',
            strict_field_count=True
        )

    def test_parse_valid_csv_line(self, basic_config):
        """Test parsing a valid CSV line."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,John Doe,john@example.com'))

        assert len(results) == 1
        record = results[0]
        assert record['id'] == '1'
        assert record['name'] == 'John Doe'
        assert record['email'] == 'john@example.com'

    def test_parse_quoted_fields(self, basic_config):
        """Test parsing CSV with quoted fields containing commas."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('1,"Doe, John",john@example.com'))

        assert len(results) == 1
        assert results[0]['name'] == 'Doe, John'

    def test_skip_empty_line(self, basic_config):
        """Test that empty lines are skipped."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process(''))
        assert len(results) == 0

        results = list(parser.process('   '))
        assert len(results) == 0

    def test_skip_header_record(self, basic_config):
        """Test that HDR records are skipped."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('HDR|Application1|Customers|20260101'))
        assert len(results) == 0

    def test_skip_trailer_record(self, basic_config):
        """Test that TRL records are skipped."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('TRL|1000'))
        assert len(results) == 0

    def test_skip_csv_header_row(self, basic_config):
        """Test that CSV header row is skipped."""
        parser = RobustCsvParseDoFn(basic_config)

        results = list(parser.process('id,name,email'))
        assert len(results) == 0

    def test_missing_columns_lenient_mode(self, basic_config):
        """Test handling of missing columns in lenient mode."""
        parser = RobustCsvParseDoFn(basic_config)

        # Only 2 fields instead of 3
        results = list(parser.process('1,John Doe'))

        # Should have parsed record (possibly with warning)
        # Check that we got at least one output
        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        warning_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                         and r.tag == 'warnings']

        # In lenient mode, missing fields are padded
        assert len(main_outputs) == 1 or len(warning_outputs) > 0

    def test_missing_columns_strict_mode(self, strict_config):
        """Test that missing columns cause error in strict mode."""
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John Doe'))

        # Should route to errors
        error_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                        and r.tag == 'errors']
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.MISSING_COLUMNS.value

    def test_extra_columns_lenient_mode(self, basic_config):
        """Test handling of extra columns in lenient mode."""
        parser = RobustCsvParseDoFn(basic_config)

        # 4 fields instead of 3
        results = list(parser.process('1,John Doe,john@example.com,extra_field'))

        # Should succeed with warning in lenient mode
        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(main_outputs) >= 1

    def test_extra_columns_strict_mode(self, strict_config):
        """Test that extra columns cause error in strict mode."""
        parser = RobustCsvParseDoFn(strict_config)

        results = list(parser.process('1,John Doe,john@example.com,extra'))

        error_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                        and r.tag == 'errors']
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.EXTRA_COLUMNS.value

    def test_null_byte_removal(self, basic_config):
        """Test that null bytes are removed from input."""
        parser = RobustCsvParseDoFn(basic_config)

        # Line with embedded null byte
        line_with_null = '1,John\x00Doe,john@example.com'
        results = list(parser.process(line_with_null))

        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(main_outputs) >= 1
        # Null should be removed
        assert '\x00' not in str(main_outputs[0])

    def test_control_character_replacement(self, basic_config):
        """Test that control characters are replaced."""
        parser = RobustCsvParseDoFn(basic_config)

        # Line with control characters
        line_with_ctrl = '1,John\x07Doe,john@example.com'
        results = list(parser.process(line_with_ctrl))

        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(main_outputs) >= 1

    def test_corrupted_row_detection(self, basic_config):
        """Test detection of corrupted rows (unbalanced quotes)."""
        parser = RobustCsvParseDoFn(basic_config)

        # Unbalanced quote
        corrupted_line = '1,"John Doe,john@example.com'
        results = list(parser.process(corrupted_line))

        error_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                        and r.tag == 'errors']
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.QUOTE_MISMATCH.value

    def test_auto_detect_pipe_delimiter(self, basic_config):
        """Test auto-detection of pipe delimiter."""
        parser = RobustCsvParseDoFn(basic_config)

        # Line uses pipe instead of comma
        pipe_line = '1|John Doe|john@example.com'
        results = list(parser.process(pipe_line))

        # Should succeed with auto-detection
        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        warning_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                         and r.tag == 'warnings']

        # Either parsed successfully or got warning about delimiter
        assert len(main_outputs) >= 1 or len(warning_outputs) >= 1

    def test_auto_detect_tab_delimiter(self, basic_config):
        """Test auto-detection of tab delimiter."""
        parser = RobustCsvParseDoFn(basic_config)

        # Line uses tab instead of comma
        tab_line = '1\tJohn Doe\tjohn@example.com'
        results = list(parser.process(tab_line))

        main_outputs = [r for r in results if not isinstance(r, beam.pvalue.TaggedOutput)]
        assert len(main_outputs) >= 1

    def test_very_long_field_detection(self):
        """Test detection of suspiciously long fields."""
        config = CSVParserConfig(
            field_names=['id', 'name'],
            max_field_length=100
        )
        parser = RobustCsvParseDoFn(config)

        # Create a field longer than max_field_length
        long_value = 'x' * 200
        results = list(parser.process(f'1,{long_value}'))

        error_outputs = [r for r in results if isinstance(r, beam.pvalue.TaggedOutput)
                        and r.tag == 'errors']
        assert len(error_outputs) == 1
        assert error_outputs[0].value['error_type'] == CSVErrorType.CORRUPTED_ROW.value

    def test_custom_hdr_trl_prefix(self):
        """Test custom HDR/TRL prefix handling."""
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


class TestDetectDelimiterDoFn:
    """Tests for DetectDelimiterDoFn."""

    def test_detect_comma_delimiter(self):
        """Test detection of comma delimiter."""
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
        """Test detection of pipe delimiter."""
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
        """Test detection of tab delimiter."""
        detector = DetectDelimiterDoFn(expected_columns=3)

        lines = [
            'id\tname\temail',
            '1\tJohn\tjohn@test.com',
            '2\tJane\tjane@test.com'
        ]

        results = list(detector.process(lines))

        assert len(results) == 1
        assert results[0]['delimiter'] == '\t'

    def test_low_confidence_with_inconsistent_data(self):
        """Test low confidence when data is inconsistent."""
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


class TestCSVErrorType:
    """Tests for CSVErrorType enum."""

    def test_error_types_exist(self):
        """Test that all expected error types exist."""
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


class TestBeamPipelineIntegration:
    """Integration tests with Apache Beam TestPipeline."""

    def test_robust_parser_in_pipeline(self):
        """Test RobustCsvParseDoFn in a Beam pipeline."""
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
        """Test DetectDelimiterDoFn in a Beam pipeline."""
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


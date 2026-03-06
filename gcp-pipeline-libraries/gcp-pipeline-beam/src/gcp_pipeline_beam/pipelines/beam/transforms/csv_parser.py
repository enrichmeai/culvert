"""
Robust CSV Parser Module

Advanced CSV parsing DoFns with comprehensive error handling for:
- Missing columns / Too many fields
- Non-UTF8 characters
- Wrong delimiters
- Corrupted/truncated rows
- Encoding issues

This module provides production-grade CSV parsing with configurable
error handling and recovery strategies.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Iterator, Optional, Set, Tuple

import apache_beam as beam

logger = logging.getLogger(__name__)


class CSVErrorType(Enum):
    """Types of CSV parsing errors."""
    FIELD_COUNT_MISMATCH = "FIELD_COUNT_MISMATCH"
    MISSING_COLUMNS = "MISSING_COLUMNS"
    EXTRA_COLUMNS = "EXTRA_COLUMNS"
    ENCODING_ERROR = "ENCODING_ERROR"
    NON_UTF8_CHARACTERS = "NON_UTF8_CHARACTERS"
    WRONG_DELIMITER = "WRONG_DELIMITER"
    CORRUPTED_ROW = "CORRUPTED_ROW"
    TRUNCATED_ROW = "TRUNCATED_ROW"
    EMPTY_ROW = "EMPTY_ROW"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"
    NULL_BYTE = "NULL_BYTE"


@dataclass
class CSVParserConfig:
    """Configuration for robust CSV parsing.

    Attributes:
        field_names: List of expected column names
        delimiter: Expected field delimiter (default: ',')
        quotechar: Quote character for fields (default: '"')
        encoding: Expected file encoding (default: 'utf-8')
        skip_hdr_trl: Skip HDR/TRL records from mainframe files
        hdr_prefix: Header record prefix (default: "HDR|")
        trl_prefix: Trailer record prefix (default: "TRL|")
        strict_field_count: Fail on field count mismatch vs padding/truncating
        max_field_length: Maximum allowed field length (detect corruption)
        detect_delimiter: Auto-detect delimiter if parsing fails
        alternative_delimiters: Delimiters to try if auto-detection enabled
        sanitize_encoding: Clean non-UTF8 characters instead of failing
        replacement_char: Character to replace invalid bytes
        strip_null_bytes: Remove null bytes from input
        max_row_length: Maximum row length (detect corruption)
    """
    field_names: List[str]
    delimiter: str = ","
    quotechar: str = '"'
    encoding: str = "utf-8"
    skip_hdr_trl: bool = True
    hdr_prefix: str = "HDR|"
    trl_prefix: str = "TRL|"
    strict_field_count: bool = False
    max_field_length: int = 65535
    detect_delimiter: bool = True
    alternative_delimiters: List[str] = None
    sanitize_encoding: bool = True
    replacement_char: str = "?"
    strip_null_bytes: bool = True
    max_row_length: int = 1048576  # 1MB

    def __post_init__(self):
        if self.alternative_delimiters is None:
            self.alternative_delimiters = ["|", "\t", ";", "^"]


class RobustCsvParseDoFn(beam.DoFn):
    """
    Production-grade CSV parser with comprehensive error handling.

    Handles common mainframe and legacy system CSV issues:
    - Field count mismatches (missing/extra columns)
    - Non-UTF8 characters from legacy encodings (EBCDIC, Latin-1)
    - Wrong or mixed delimiters
    - Corrupted/truncated rows
    - Null bytes in data
    - Quote mismatches

    Outputs:
        Main: Dict[str, str] - Successfully parsed records
        'errors': Dict - Records that failed to parse with error details
        'warnings': Dict - Records parsed with warnings (sanitized data)

    Metrics:
        csv_parse/success: Successfully parsed records
        csv_parse/errors: Records that failed to parse
        csv_parse/warnings: Records parsed with warnings
        csv_parse/skipped: HDR/TRL or empty records skipped
        csv_parse/encoding_fixed: Records with encoding issues fixed
        csv_parse/delimiter_corrected: Records with delimiter auto-corrected

    Example:
        >>> config = CSVParserConfig(
        ...     field_names=['id', 'name', 'email'],
        ...     delimiter=',',
        ...     sanitize_encoding=True,
        ...     detect_delimiter=True
        ... )
        >>> pipeline | 'ParseCSV' >> beam.ParDo(
        ...     RobustCsvParseDoFn(config)
        ... ).with_outputs('main', 'errors', 'warnings')
    """

    def __init__(self, config: CSVParserConfig):
        """
        Initialize robust CSV parser.

        Args:
            config: CSVParserConfig with parsing options
        """
        super().__init__()
        self.config = config

        # Metrics
        self.success = beam.metrics.Metrics.counter("csv_parse", "success")
        self.errors = beam.metrics.Metrics.counter("csv_parse", "errors")
        self.warnings = beam.metrics.Metrics.counter("csv_parse", "warnings")
        self.skipped = beam.metrics.Metrics.counter("csv_parse", "skipped")
        self.encoding_fixed = beam.metrics.Metrics.counter("csv_parse", "encoding_fixed")
        self.delimiter_corrected = beam.metrics.Metrics.counter("csv_parse", "delimiter_corrected")

    def process(self, line: str) -> Iterator[Any]:
        """
        Parse a CSV line with comprehensive error handling.

        Args:
            line: Raw CSV line from file

        Yields:
            Dict[str, str]: Parsed record (main output)
            TaggedOutput('errors', ...): Failed records
            TaggedOutput('warnings', ...): Records with warnings
        """
        parse_warnings: List[str] = []
        original_line = line

        try:
            # Pre-validation checks
            skip_reason = self._should_skip_line(line)
            if skip_reason:
                self.skipped.inc()
                return

            # Sanitize line before parsing
            line, sanitize_warnings = self._sanitize_line(line)
            parse_warnings.extend(sanitize_warnings)

            # Check for corruption indicators
            corruption_error = self._check_corruption(line)
            if corruption_error:
                self.errors.inc()
                yield beam.pvalue.TaggedOutput("errors", {
                    "error_type": corruption_error.value,
                    "error": f"Line appears corrupted: {corruption_error.value}",
                    "raw_line": original_line[:1000],  # Truncate for storage
                    "line_length": len(original_line)
                })
                return

            # Attempt to parse with configured delimiter
            record, parse_error = self._parse_line(line, self.config.delimiter)

            # If parsing failed and auto-detection is enabled, try alternatives
            if parse_error and self.config.detect_delimiter:
                for alt_delimiter in self.config.alternative_delimiters:
                    record, alt_error = self._parse_line(line, alt_delimiter)
                    if not alt_error:
                        parse_warnings.append(
                            f"Used alternative delimiter '{alt_delimiter}' instead of '{self.config.delimiter}'"
                        )
                        self.delimiter_corrected.inc()
                        break
                else:
                    # All delimiters failed
                    self.errors.inc()
                    yield beam.pvalue.TaggedOutput("errors", {
                        "error_type": CSVErrorType.WRONG_DELIMITER.value,
                        "error": "Failed to parse with any known delimiter",
                        "raw_line": original_line[:1000],
                        "tried_delimiters": [self.config.delimiter] + self.config.alternative_delimiters
                    })
                    return
            elif parse_error:
                self.errors.inc()
                yield beam.pvalue.TaggedOutput("errors", parse_error)
                return

            # Validate field count
            validation_result = self._validate_field_count(record, original_line)
            if validation_result['error'] and self.config.strict_field_count:
                self.errors.inc()
                yield beam.pvalue.TaggedOutput("errors", validation_result['error'])
                return
            elif validation_result['warning']:
                parse_warnings.append(validation_result['warning'])
                record = validation_result.get('adjusted_record', record)

            # Validate field lengths (detect corruption)
            length_error = self._validate_field_lengths(record, original_line)
            if length_error:
                self.errors.inc()
                yield beam.pvalue.TaggedOutput("errors", length_error)
                return

            # Success - yield record
            if parse_warnings:
                self.warnings.inc()
                yield beam.pvalue.TaggedOutput("warnings", {
                    "record": record,
                    "warnings": parse_warnings,
                    "original_line": original_line[:500]
                })

            self.success.inc()
            yield record

        except Exception as e:
            logger.error(f"Unexpected error parsing CSV line: {e}")
            self.errors.inc()
            yield beam.pvalue.TaggedOutput("errors", {
                "error_type": CSVErrorType.PARSE_ERROR.value,
                "error": str(e),
                "raw_line": original_line[:1000] if original_line else "N/A"
            })

    def _should_skip_line(self, line: str) -> Optional[str]:
        """Check if line should be skipped (HDR/TRL, empty, header row)."""
        if not line or line.strip() == "":
            return "empty_line"

        stripped = line.strip()

        # Skip HDR/TRL records
        if self.config.skip_hdr_trl:
            if stripped.startswith(self.config.hdr_prefix):
                return "header_record"
            if stripped.startswith(self.config.trl_prefix):
                return "trailer_record"

        # Skip if this is the CSV header row
        try:
            f = io.StringIO(line)
            reader = csv.reader(f, delimiter=self.config.delimiter)
            row = next(reader, None)
            if row and row == self.config.field_names:
                return "csv_header"
        except Exception:
            pass  # Will be handled in main parsing

        return None

    def _sanitize_line(self, line: str) -> Tuple[str, List[str]]:
        """
        Sanitize line by fixing common encoding issues.

        Returns:
            Tuple of (sanitized_line, list_of_warnings)
        """
        warnings = []
        original = line

        # Remove null bytes
        if self.config.strip_null_bytes and '\x00' in line:
            line = line.replace('\x00', '')
            warnings.append("Removed null bytes from line")
            self.encoding_fixed.inc()

        # Handle non-UTF8 characters
        if self.config.sanitize_encoding:
            try:
                # Check if line has problematic characters by re-encoding
                line.encode('utf-8')
            except UnicodeEncodeError:
                # Replace problematic characters
                line = line.encode('utf-8', errors='replace').decode('utf-8')
                warnings.append("Replaced non-UTF8 characters")
                self.encoding_fixed.inc()

        # Remove control characters (except tab)
        control_char_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
        if control_char_pattern.search(line):
            line = control_char_pattern.sub(self.config.replacement_char, line)
            warnings.append("Replaced control characters")

        return line, warnings

    def _check_corruption(self, line: str) -> Optional[CSVErrorType]:
        """Check for signs of data corruption."""
        # Line too long (likely binary data or corruption)
        if len(line) > self.config.max_row_length:
            return CSVErrorType.CORRUPTED_ROW

        # Check for unbalanced quotes (simple check)
        quote_count = line.count(self.config.quotechar)
        if quote_count % 2 != 0:
            return CSVErrorType.QUOTE_MISMATCH

        # Check for suspiciously high proportion of non-printable characters
        non_printable = sum(1 for c in line if ord(c) < 32 and c not in '\t\n\r')
        if len(line) > 10 and non_printable / len(line) > 0.1:
            return CSVErrorType.CORRUPTED_ROW

        return None

    def _parse_line(
        self,
        line: str,
        delimiter: str
    ) -> Tuple[Optional[Dict[str, str]], Optional[Dict]]:
        """
        Parse a single line with given delimiter.

        Returns:
            Tuple of (parsed_record or None, error_dict or None)
        """
        try:
            f = io.StringIO(line)
            reader = csv.reader(
                f,
                delimiter=delimiter,
                quotechar=self.config.quotechar
            )

            row = next(reader, None)
            if row is None:
                return None, {
                    "error_type": CSVErrorType.EMPTY_ROW.value,
                    "error": "Could not parse row",
                    "raw_line": line[:1000]
                }

            # Check for remaining data (shouldn't have multiple rows)
            remaining = next(reader, None)
            if remaining is not None:
                return None, {
                    "error_type": CSVErrorType.CORRUPTED_ROW.value,
                    "error": "Line contains embedded newlines or multiple rows",
                    "raw_line": line[:1000]
                }

            # Create record dict
            if len(row) == len(self.config.field_names):
                record = dict(zip(self.config.field_names, row))
                return record, None
            else:
                # Will be handled by field count validation
                # Create partial record for analysis
                record = {}
                for i, value in enumerate(row):
                    if i < len(self.config.field_names):
                        record[self.config.field_names[i]] = value
                    else:
                        record[f"_extra_field_{i}"] = value

                return record, None  # Let field count validation handle it

        except csv.Error as e:
            return None, {
                "error_type": CSVErrorType.PARSE_ERROR.value,
                "error": f"CSV parsing error: {str(e)}",
                "raw_line": line[:1000]
            }
        except Exception as e:
            return None, {
                "error_type": CSVErrorType.PARSE_ERROR.value,
                "error": f"Unexpected parse error: {str(e)}",
                "raw_line": line[:1000]
            }

    def _validate_field_count(
        self,
        record: Dict[str, str],
        original_line: str
    ) -> Dict[str, Any]:
        """
        Validate that record has correct number of fields.

        Returns dict with 'error', 'warning', and optionally 'adjusted_record'.
        """
        expected = len(self.config.field_names)
        # Count actual fields (including extra fields)
        actual = len([k for k in record.keys() if not k.startswith('_extra_')])
        extra = len([k for k in record.keys() if k.startswith('_extra_')])
        total = actual + extra

        if total == expected:
            return {"error": None, "warning": None}

        if total < expected:
            # Missing fields
            missing_fields = self.config.field_names[total:]

            if self.config.strict_field_count:
                return {
                    "error": {
                        "error_type": CSVErrorType.MISSING_COLUMNS.value,
                        "error": f"Missing {expected - total} fields",
                        "expected_fields": expected,
                        "actual_fields": total,
                        "missing_fields": missing_fields,
                        "raw_line": original_line[:1000]
                    },
                    "warning": None
                }
            else:
                # Pad with empty strings
                adjusted = record.copy()
                for field in missing_fields:
                    adjusted[field] = ""
                return {
                    "error": None,
                    "warning": f"Padded {len(missing_fields)} missing fields with empty values",
                    "adjusted_record": adjusted
                }
        else:
            # Extra fields
            if self.config.strict_field_count:
                return {
                    "error": {
                        "error_type": CSVErrorType.EXTRA_COLUMNS.value,
                        "error": f"Found {extra} extra fields",
                        "expected_fields": expected,
                        "actual_fields": total,
                        "raw_line": original_line[:1000]
                    },
                    "warning": None
                }
            else:
                # Remove extra fields
                adjusted = {k: v for k, v in record.items()
                          if not k.startswith('_extra_')}
                return {
                    "error": None,
                    "warning": f"Truncated {extra} extra fields",
                    "adjusted_record": adjusted
                }

    def _validate_field_lengths(
        self,
        record: Dict[str, str],
        original_line: str
    ) -> Optional[Dict]:
        """Check for abnormally long fields (corruption indicator)."""
        for field_name, value in record.items():
            if len(value) > self.config.max_field_length:
                return {
                    "error_type": CSVErrorType.CORRUPTED_ROW.value,
                    "error": f"Field '{field_name}' exceeds max length ({len(value)} > {self.config.max_field_length})",
                    "field_name": field_name,
                    "field_length": len(value),
                    "max_allowed": self.config.max_field_length,
                    "raw_line": original_line[:1000]
                }
        return None


class DetectDelimiterDoFn(beam.DoFn):
    """
    Analyzes sample lines to detect the correct CSV delimiter.

    Useful for pre-flight validation or when delimiter is unknown.

    Outputs:
        Main: Dict with detected delimiter and confidence score
    """

    COMMON_DELIMITERS = [",", "|", "\t", ";", "^", ":"]

    def __init__(self, expected_columns: int):
        """
        Initialize delimiter detector.

        Args:
            expected_columns: Expected number of columns in CSV
        """
        super().__init__()
        self.expected_columns = expected_columns

    def process(self, lines: List[str]) -> Iterator[Dict[str, Any]]:
        """
        Analyze lines to detect delimiter.

        Args:
            lines: Sample of lines from the file

        Yields:
            Dict with 'delimiter', 'confidence', and 'analysis'
        """
        results = {}

        for delimiter in self.COMMON_DELIMITERS:
            counts = []
            for line in lines:
                if line.strip():
                    try:
                        f = io.StringIO(line)
                        reader = csv.reader(f, delimiter=delimiter)
                        row = next(reader, [])
                        counts.append(len(row))
                    except Exception:
                        counts.append(0)

            if counts:
                avg_count = sum(counts) / len(counts)
                variance = sum((c - avg_count) ** 2 for c in counts) / len(counts)
                consistency = 1 / (1 + variance)
                match_score = 1 - abs(avg_count - self.expected_columns) / max(self.expected_columns, 1)

                results[delimiter] = {
                    "avg_fields": avg_count,
                    "consistency": consistency,
                    "match_score": max(0, match_score),
                    "combined_score": consistency * max(0, match_score)
                }

        if results:
            best_delimiter = max(results.keys(), key=lambda d: results[d]["combined_score"])
            yield {
                "delimiter": best_delimiter,
                "confidence": results[best_delimiter]["combined_score"],
                "analysis": results
            }
        else:
            yield {
                "delimiter": ",",
                "confidence": 0.0,
                "analysis": {},
                "warning": "Could not detect delimiter, defaulting to comma"
            }


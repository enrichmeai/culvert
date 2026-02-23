"""
Parsers Module

CSV parsing and line-parsing DoFns for Apache Beam pipelines.
"""

import logging
import csv
import io
from typing import Dict, List, Any, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class ParseCsvLine(beam.DoFn):
    """
    Parse a CSV line into a record dictionary.

    This is typically the first transform after reading files from GCS.
    Converts raw text lines to structured records with proper error handling.

    Library provides the mechanism. Pipeline can configure:
    - field_names: Column names
    - delimiter: Field delimiter
    - skip_hdr_trl: Whether to skip header/trailer records
    - hdr_prefix: Header line prefix (default: "HDR|")
    - trl_prefix: Trailer line prefix (default: "TRL|")

    Attributes:
        field_names: List of column names
        delimiter: CSV delimiter character (default: ',')
        skip_hdr_trl: Skip HDR/TRL records (default: True)
        hdr_prefix: Header record prefix (default: "HDR|")
        trl_prefix: Trailer record prefix (default: "TRL|")

    Outputs:
        Main: Dict[str, str] - Parsed record with field names as keys
        'errors': Dict - Error records with parsing errors

    Metrics:
        parse/errors: Counter of parse failures
        parse/success: Counter of successful parses
        parse/skipped: Counter of skipped lines (HDR/TRL, empty, header row)

    Example:
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(
        ...             field_names=['id', 'name', 'email'],
        ...             delimiter=',',
        ...             skip_hdr_trl=True
        ...         )).with_outputs('main', 'errors')
    """

    def __init__(
        self,
        field_names: List[str],
        delimiter: str = ",",
        skip_hdr_trl: bool = True,
        hdr_prefix: str = "HDR|",
        trl_prefix: str = "TRL|"
    ):
        """
        Initialize CSV parser.

        Args:
            field_names: List of column names for the CSV
            delimiter: CSV delimiter character (default: comma)
            skip_hdr_trl: Skip HDR/TRL records (default: True)
            hdr_prefix: Header record prefix (default: "HDR|")
            trl_prefix: Trailer record prefix (default: "TRL|")

        Example:
            >>> parser = ParseCsvLine(
            ...     field_names=['id', 'name', 'email'],
            ...     delimiter=',',
            ...     skip_hdr_trl=True
            ... )

            # With custom prefixes:
            >>> parser = ParseCsvLine(
            ...     field_names=['id', 'name'],
            ...     hdr_prefix="HEADER:",
            ...     trl_prefix="FOOTER:"
            ... )
        """
        super().__init__()
        self.field_names = field_names
        self.delimiter = delimiter
        self.skip_hdr_trl = skip_hdr_trl
        self.hdr_prefix = hdr_prefix
        self.trl_prefix = trl_prefix
        self.parse_errors = beam.metrics.Metrics.counter("parse", "errors")
        self.parse_success = beam.metrics.Metrics.counter("parse", "success")
        self.parse_skipped = beam.metrics.Metrics.counter("parse", "skipped")

    def process(self, line: str) -> Iterator[Any]:
        """
        Parse a CSV line into a record dictionary.

        Handles CSV parsing with quoted fields, empty lines, and field
        count mismatches. Uses Python's csv module for robust parsing.
        Optionally skips HDR/TRL records from extract files.

        Args:
            line: Raw CSV line from file

        Yields:
            Dict[str, str]: Parsed record with field names as keys
            TaggedOutput('errors', ...): Error records

        Example:
            >>> parser = ParseCsvLine(['id', 'name'])
            >>> list(parser.process('1,John'))
            [{'id': '1', 'name': 'John'}]

            >>> list(parser.process('HDR|Application1|Customer|20260101'))
            []  # Skipped

            >>> list(parser.process('incomplete'))
            [TaggedOutput('errors', {...})]
        """
        try:
            # Skip empty lines
            if not line or line.strip() == "":
                self.parse_skipped.inc()
                return

            stripped_line = line.strip()

            # Skip HDR/TRL records if enabled
            if self.skip_hdr_trl:
                if stripped_line.startswith(self.hdr_prefix) or stripped_line.startswith(self.trl_prefix):
                    self.parse_skipped.inc()
                    return

            # Use csv module for robust parsing with quoted field support
            f = io.StringIO(line)
            reader = csv.reader(f, delimiter=self.delimiter)

            for row in reader:
                # Skip if this looks like the header row
                if row == self.field_names:
                    self.parse_skipped.inc()
                    return

                if len(row) == len(self.field_names):
                    record = dict(zip(self.field_names, row))
                    self.parse_success.inc()
                    yield record
                else:
                    logger.warning(
                        f"Field count mismatch: expected {len(self.field_names)}, "
                        f"got {len(row)}"
                    )
                    self.parse_errors.inc()
                    yield beam.pvalue.TaggedOutput("errors", {
                        "error": "Field count mismatch",
                        "expected": len(self.field_names),
                        "actual": len(row),
                        "raw_line": line
                    })

        except Exception as e:
            logger.error(f"Error parsing CSV line: {e}")
            self.parse_errors.inc()
            yield beam.pvalue.TaggedOutput("errors", {
                "error": str(e),
                "raw_line": line
            })


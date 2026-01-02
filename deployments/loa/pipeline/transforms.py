"""
LOA Pipeline Transforms.

Apache Beam DoFn classes for LOA entity processing.
Uses library components - no duplication.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Iterator

import apache_beam as beam

from gdw_data_core.core.file_management import HDRTRLParser

from ..validation import LOAValidator
from ..schema import LOA_SCHEMAS

logger = logging.getLogger(__name__)


class ValidateFileDoFn(beam.DoFn):
    """
    Validate file structure (HDR/TRL, record count, checksum).

    Outputs:
        - 'valid': File metadata if valid
        - 'invalid': Error info if invalid
    """

    def __init__(self, entity: str):
        self.entity = entity
        self.parser = HDRTRLParser()
        self.validator = None

    def setup(self):
        self.validator = LOAValidator()

    def process(self, file_content: str):
        lines = file_content.split('\n')
        lines = [line for line in lines if line.strip()]

        result = self.validator.validate_file(lines, self.entity)

        if result.is_valid:
            metadata = self.parser.parse_file_lines(lines)
            yield beam.pvalue.TaggedOutput('valid', {
                'lines': lines,
                'metadata': metadata,
                'record_count': result.record_count,
            })
        else:
            yield beam.pvalue.TaggedOutput('invalid', {
                'errors': result.errors,
                'warnings': result.warnings,
            })


class ParseAndValidateRecordDoFn(beam.DoFn):
    """
    Parse CSV line and validate record.

    Outputs:
        - 'valid': Valid record with audit columns
        - 'errors': Invalid record with error details
    """

    def __init__(
        self,
        entity: str,
        headers: List[str],
        run_id: str,
        source_file: str
    ):
        self.entity = entity
        self.headers = headers
        self.run_id = run_id
        self.source_file = source_file
        self.validator = None
        self.schema = None

        # Metrics
        self.valid_count = beam.metrics.Metrics.counter("loa", "valid_records")
        self.error_count = beam.metrics.Metrics.counter("loa", "error_records")

    def setup(self):
        self.validator = LOAValidator()
        self.schema = LOA_SCHEMAS.get(self.entity)

    def process(self, line: str) -> Iterator[Dict[str, Any]]:
        line = line.strip()

        # Skip HDR/TRL and empty lines
        if not line or line.startswith('HDR|') or line.startswith('TRL|'):
            return

        # Skip CSV header row
        values = line.split(',')
        if values == self.headers:
            return

        # Parse CSV to record
        if len(values) != len(self.headers):
            self.error_count.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'line': line,
                'errors': [f"Column count mismatch: expected {len(self.headers)}, got {len(values)}"],
                'entity': self.entity,
            })
            return

        record = dict(zip(self.headers, values))

        # Validate record
        valid_records, error_records = self.validator.validate_records([record], self.entity)

        if error_records:
            self.error_count.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'record': record,
                'errors': error_records[0]['errors'],
                'entity': self.entity,
            })
        else:
            self.valid_count.inc()
            # Add audit columns
            record['_run_id'] = self.run_id
            record['_source_file'] = self.source_file
            record['_processed_at'] = datetime.utcnow().isoformat()
            yield beam.pvalue.TaggedOutput('valid', record)


class AddExtractDateDoFn(beam.DoFn):
    """Add _extract_date from parsed header metadata."""

    def __init__(self, extract_date: str):
        self.extract_date = extract_date

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        record['_extract_date'] = self.extract_date
        yield record


class FilterByEventTypeDoFn(beam.DoFn):
    """
    Filter records for event_transaction_excess FDP.

    Only passes records where event_type is not null.
    """

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        if record.get('event_type'):
            yield record


class FilterByPortfolioDoFn(beam.DoFn):
    """
    Filter records for portfolio_account_excess FDP.

    Only passes records where portfolio_id is not null.
    """

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        if record.get('portfolio_id'):
            yield record


class CreateEventKeyDoFn(beam.DoFn):
    """Create composite event_key for event_transaction_excess FDP."""

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        event_key = (
            f"{record.get('application_id', 'NA')}-"
            f"{record.get('event_type', 'NA')}-"
            f"{record.get('event_date', 'NA')}"
        )
        record['event_key'] = event_key
        yield record


class CreatePortfolioKeyDoFn(beam.DoFn):
    """Create composite portfolio_key for portfolio_account_excess FDP."""

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        portfolio_key = (
            f"{record.get('portfolio_id', 'NA')}-"
            f"{record.get('account_id', 'NA')}"
        )
        record['portfolio_key'] = portfolio_key
        yield record


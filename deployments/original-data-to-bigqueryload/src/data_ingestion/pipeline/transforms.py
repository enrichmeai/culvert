"""
Generic Pipeline Transforms.

Apache Beam DoFn classes for Generic entity processing.
Uses library components - no duplication.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Iterator

import apache_beam as beam

from gcp_pipeline_beam.file_management import HDRTRLParser

from ..validation import GenericValidator
from ..schema import ENTITY_SCHEMAS

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
        self.validator = GenericValidator()

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

        self.valid_count = beam.metrics.Metrics.counter("generic", "valid_records")
        self.error_count = beam.metrics.Metrics.counter("generic", "error_records")

    def setup(self):
        self.validator = GenericValidator()
        self.schema = ENTITY_SCHEMAS.get(self.entity)

    def process(self, line: str) -> Iterator[Dict[str, Any]]:
        line = line.strip()

        # Skip HDR/TRL and empty lines
        if not line or line.startswith('HDR|') or line.startswith('TRL|'):
            return

        # Skip CSV header row
        values = line.split(',')
        if values == self.headers:
            return

        # Parse CSV
        if len(values) != len(self.headers):
            self.error_count.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'line': line,
                'error': f'Field count mismatch: expected {len(self.headers)}, got {len(values)}',
                '_run_id': self.run_id,
                '_source_file': self.source_file,
                '_processed_at': datetime.now(tz=timezone.utc).isoformat(),
            })
            return

        record = dict(zip(self.headers, values))

        # Validate record
        errors = self.validator.record_validator.validate_record(record, self.entity)

        if errors:
            self.error_count.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                **record,
                'errors': errors,
                '_run_id': self.run_id,
                '_source_file': self.source_file,
                '_processed_at': datetime.now(tz=timezone.utc).isoformat(),
            })
        else:
            self.valid_count.inc()
            yield beam.pvalue.TaggedOutput('valid', {
                **record,
                '_run_id': self.run_id,
                '_source_file': self.source_file,
                '_processed_at': datetime.now(tz=timezone.utc).isoformat(),
            })


class AddAuditColumnsDoFn(beam.DoFn):
    """Add audit columns to records."""

    def __init__(self, run_id: str, source_file: str):
        self.run_id = run_id
        self.source_file = source_file

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        yield {
            **record,
            '_run_id': self.run_id,
            '_source_file': self.source_file,
            '_processed_at': datetime.now(tz=timezone.utc).isoformat(),
        }


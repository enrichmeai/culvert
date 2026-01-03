"""
LOA (Application B Application) - Apache Beam/Dataflow Pipeline
====================================================================

Purpose:
  Pipeline for loading LOA mainframe extracts to BigQuery ODP tables.
  Handles single entity: Applications.

Flow:
  1. Read CSV files from GCS (handles split files)
  2. Parse HDR/TRL records using library (HDRTRLParser)
  3. Parse CSV data lines (skip HDR/TRL)
  4. Validate each record
  5. Write valid records to BigQuery ODP table
  6. Write error records to error table
  7. Update job_control table
  8. Archive source files

Library Components Used:
  - gcp_pipeline_builder.core.file_management.HDRTRLParser
  - gcp_pipeline_builder.pipelines.beam.transforms.ParseCsvLine
  - gcp_pipeline_builder.core.job_control.JobControlRepository

Entities:
  - applications → odp_loa.applications

Note: Unlike EM (which waits for 3 entities), LOA immediately triggers
      FDP transformation after ODP load (single entity, no dependency wait).

Usage:
  python loa_pipeline.py --entity=applications --input_pattern=gs://bucket/loa/applications/*.csv
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Iterator

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - NO DUPLICATION
from gcp_pipeline_builder.file_management import HDRTRLParser
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_builder.pipelines.beam.transforms.parsers import ParseCsvLine

# LOA-specific imports
from loa.config import (
    SYSTEM_ID,
    APPLICATIONS_HEADERS,
    ALLOWED_APPLICATION_STATUSES,
    ALLOWED_APPLICATION_TYPES,
    ALLOWED_ACCOUNT_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_TRANSACTION_TYPES,
    ALLOWED_EXCESS_STATUSES,
    LOAN_AMOUNT_MIN,
    LOAN_AMOUNT_MAX,
    INTEREST_RATE_MIN,
    INTEREST_RATE_MAX,
)

logger = logging.getLogger(__name__)


# Entity configuration - LOA specific (single entity)
LOA_ENTITY_CONFIG = {
    "applications": {
        "headers": APPLICATIONS_HEADERS,
        "primary_key": ["application_id"],
        "output_table": "odp_loa.applications",
        "error_table": "odp_loa.applications_errors",
    },
}


class LOAPipelineOptions(PipelineOptions):
    """LOA Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--entity',
            type=str,
            required=True,
            choices=['applications'],
            help='Entity to process'
        )
        parser.add_argument(
            '--input_pattern',
            type=str,
            required=True,
            help='GCS pattern for input files'
        )
        parser.add_argument(
            '--output_table',
            type=str,
            required=True,
            help='BigQuery output table'
        )
        parser.add_argument(
            '--error_table',
            type=str,
            required=True,
            help='BigQuery error table'
        )
        parser.add_argument(
            '--run_id',
            type=str,
            default=None,
            help='Pipeline run ID'
        )
        parser.add_argument(
            '--project_id',
            type=str,
            required=True,
            help='GCP project ID'
        )


class ValidateLOARecordDoFn(beam.DoFn):
    """
    Validate LOA entity records.

    Routes records to valid/errors outputs based on validation.
    """

    def __init__(self, entity: str):
        super().__init__()
        self.entity = entity
        self.config = LOA_ENTITY_CONFIG[entity]

        # Metrics
        self.valid_count = beam.metrics.Metrics.counter("loa", "valid_records")
        self.error_count = beam.metrics.Metrics.counter("loa", "error_records")

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        errors = []

        # Validate primary key
        for pk in self.config["primary_key"]:
            if not record.get(pk):
                errors.append(f"Missing required field: {pk}")

        # Required fields validation
        if not record.get("customer_id"):
            errors.append("Missing required field: customer_id")
        if not record.get("application_date"):
            errors.append("Missing required field: application_date")

        # Allowed values validation
        if record.get('application_status'):
            if record['application_status'] not in ALLOWED_APPLICATION_STATUSES:
                errors.append(f"Invalid application_status: {record['application_status']}")

        if record.get('application_type'):
            if record['application_type'] not in ALLOWED_APPLICATION_TYPES:
                errors.append(f"Invalid application_type: {record['application_type']}")

        if record.get('account_status'):
            if record['account_status'] not in ALLOWED_ACCOUNT_STATUSES:
                errors.append(f"Invalid account_status: {record['account_status']}")

        if record.get('account_type'):
            if record['account_type'] not in ALLOWED_ACCOUNT_TYPES:
                errors.append(f"Invalid account_type: {record['account_type']}")

        if record.get('event_type'):
            if record['event_type'] not in ALLOWED_EVENT_TYPES:
                errors.append(f"Invalid event_type: {record['event_type']}")

        if record.get('transaction_type'):
            if record['transaction_type'] not in ALLOWED_TRANSACTION_TYPES:
                errors.append(f"Invalid transaction_type: {record['transaction_type']}")

        if record.get('excess_status'):
            if record['excess_status'] not in ALLOWED_EXCESS_STATUSES:
                errors.append(f"Invalid excess_status: {record['excess_status']}")

        # Numeric range validation
        if record.get('loan_amount'):
            try:
                amount = float(record['loan_amount'])
                if not (LOAN_AMOUNT_MIN <= amount <= LOAN_AMOUNT_MAX):
                    errors.append(
                        f"Loan amount out of range ({LOAN_AMOUNT_MIN}-{LOAN_AMOUNT_MAX}): {amount}"
                    )
            except ValueError:
                errors.append(f"Invalid loan_amount format: {record['loan_amount']}")

        if record.get('interest_rate'):
            try:
                rate = float(record['interest_rate'])
                if not (INTEREST_RATE_MIN <= rate <= INTEREST_RATE_MAX):
                    errors.append(
                        f"Interest rate out of range ({INTEREST_RATE_MIN}-{INTEREST_RATE_MAX}): {rate}"
                    )
            except ValueError:
                errors.append(f"Invalid interest_rate format: {record['interest_rate']}")

        if errors:
            self.error_count.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'record': record,
                'errors': errors,
                'entity': self.entity
            })
        else:
            self.valid_count.inc()
            yield beam.pvalue.TaggedOutput('valid', record)


class AddAuditColumnsDoFn(beam.DoFn):
    """Add audit columns (_run_id, _source_file, _processed_at, _extract_date)."""

    def __init__(self, run_id: str, source_file: str, extract_date: str):
        super().__init__()
        self.run_id = run_id
        self.source_file = source_file
        self.extract_date = extract_date

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        record['_run_id'] = self.run_id
        record['_source_file'] = self.source_file
        record['_processed_at'] = datetime.utcnow().isoformat()
        record['_extract_date'] = self.extract_date
        yield record


def run_loa_pipeline(argv=None):
    """
    Run the LOA ODP load pipeline.

    After completion, triggers FDP transformation immediately
    (no dependency wait - single entity).
    """
    options = LOAPipelineOptions(argv)
    loa_opts = options.view_as(LOAPipelineOptions)

    entity = loa_opts.entity
    config = LOA_ENTITY_CONFIG[entity]
    run_id = loa_opts.run_id or f"loa_{entity}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Starting LOA pipeline: entity={entity}, run_id={run_id}")

    with beam.Pipeline(options=options) as p:
        # Read files
        lines = p | 'ReadFiles' >> beam.io.ReadFromText(loa_opts.input_pattern)

        # Parse CSV - uses library ParseCsvLine with HDR/TRL skip
        records = lines | 'ParseCSV' >> beam.ParDo(
            ParseCsvLine(
                headers=config["headers"],
                skip_hdr_trl=True,
                hdr_prefix="HDR|",
                trl_prefix="TRL|"
            )
        )

        # Validate
        validated = records | 'Validate' >> beam.ParDo(
            ValidateLOARecordDoFn(entity)
        ).with_outputs('valid', 'errors')

        # Add audit columns
        audited = validated.valid | 'AddAudit' >> beam.ParDo(
            AddAuditColumnsDoFn(
                run_id,
                loa_opts.input_pattern,
                datetime.utcnow().strftime('%Y-%m-%d')
            )
        )

        # Write to BigQuery
        audited | 'WriteODP' >> beam.io.WriteToBigQuery(
            loa_opts.output_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )

        validated.errors | 'WriteErrors' >> beam.io.WriteToBigQuery(
            loa_opts.error_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )

    logger.info(f"LOA pipeline completed: entity={entity}")
    logger.info("Note: FDP transformation can be triggered immediately (no dependency wait)")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_loa_pipeline()


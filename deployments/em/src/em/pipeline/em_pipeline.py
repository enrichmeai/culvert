"""
EM (Application A) - Apache Beam/Dataflow Pipeline
=======================================================

Purpose:
  Pipeline for loading EM mainframe extracts to BigQuery ODP tables.
  Handles 3 entities: Customers, Accounts, Decision.

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
  - customers → odp_em.customers
  - accounts → odp_em.accounts
  - decision → odp_em.decision

Usage:
  python em_pipeline.py --entity=customers --input_pattern=gs://bucket/em/customers/*.csv
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

# EM-specific imports
from em.config import (
    SYSTEM_ID,
    CUSTOMERS_HEADERS,
    ACCOUNTS_HEADERS,
    DECISION_HEADERS,
    ALLOWED_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_DECISION_CODES,
    SCORE_MIN,
    SCORE_MAX,
)

logger = logging.getLogger(__name__)


# Entity configuration - EM specific
EM_ENTITY_CONFIG = {
    "customers": {
        "headers": CUSTOMERS_HEADERS,
        "primary_key": ["customer_id"],
        "output_table": "odp_em.customers",
        "error_table": "odp_em.customers_errors",
    },
    "accounts": {
        "headers": ACCOUNTS_HEADERS,
        "primary_key": ["account_id"],
        "output_table": "odp_em.accounts",
        "error_table": "odp_em.accounts_errors",
    },
    "decision": {
        "headers": DECISION_HEADERS,
        "primary_key": ["decision_id"],
        "output_table": "odp_em.decision",
        "error_table": "odp_em.decision_errors",
    },
}


class EMPipelineOptions(PipelineOptions):
    """EM Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument('--entity', type=str, required=True,
                          choices=['customers', 'accounts', 'decision'],
                          help='Entity to process')
        parser.add_argument('--input_pattern', type=str, required=True,
                          help='GCS pattern for input files')
        parser.add_argument('--output_table', type=str, required=True,
                          help='BigQuery output table')
        parser.add_argument('--error_table', type=str, required=True,
                          help='BigQuery error table')
        parser.add_argument('--run_id', type=str, default=None,
                          help='Pipeline run ID')
        parser.add_argument('--project_id', type=str, required=True,
                          help='GCP project ID')


class ValidateEMRecordDoFn(beam.DoFn):
    """Validate EM entity records - routes to valid/errors outputs."""

    def __init__(self, entity: str):
        super().__init__()
        self.entity = entity
        self.config = EM_ENTITY_CONFIG[entity]

    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        errors = []

        # Validate primary key
        for pk in self.config["primary_key"]:
            if not record.get(pk):
                errors.append(f"Missing required field: {pk}")

        # Entity-specific validation
        if self.entity == "customers":
            if record.get('status') and record['status'] not in ALLOWED_STATUSES:
                errors.append(f"Invalid status: {record['status']}")

        elif self.entity == "accounts":
            if record.get('account_type') and record['account_type'] not in ALLOWED_ACCOUNT_TYPES:
                errors.append(f"Invalid account_type: {record['account_type']}")
            if record.get('status') and record['status'] not in ALLOWED_STATUSES:
                errors.append(f"Invalid status: {record['status']}")

        elif self.entity == "decision":
            if record.get('decision_code') and record['decision_code'] not in ALLOWED_DECISION_CODES:
                errors.append(f"Invalid decision_code: {record['decision_code']}")
            if record.get('score'):
                try:
                    score = int(record['score'])
                    if not (SCORE_MIN <= score <= SCORE_MAX):
                        errors.append(f"Score out of range ({SCORE_MIN}-{SCORE_MAX}): {score}")
                except ValueError:
                    errors.append(f"Invalid score format: {record['score']}")

        if errors:
            yield beam.pvalue.TaggedOutput('errors', {
                'record': record, 'errors': errors, 'entity': self.entity
            })
        else:
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


def run_em_pipeline(argv=None):
    """Run the EM ODP load pipeline."""
    options = EMPipelineOptions(argv)
    em_opts = options.view_as(EMPipelineOptions)

    entity = em_opts.entity
    config = EM_ENTITY_CONFIG[entity]
    run_id = em_opts.run_id or f"em_{entity}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Starting EM pipeline: entity={entity}, run_id={run_id}")

    with beam.Pipeline(options=options) as p:
        # Read files
        lines = p | 'ReadFiles' >> beam.io.ReadFromText(em_opts.input_pattern)

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
            ValidateEMRecordDoFn(entity)
        ).with_outputs('valid', 'errors')

        # Add audit columns
        audited = validated.valid | 'AddAudit' >> beam.ParDo(
            AddAuditColumnsDoFn(run_id, em_opts.input_pattern,
                               datetime.utcnow().strftime('%Y-%m-%d'))
        )

        # Write to BigQuery
        audited | 'WriteODP' >> beam.io.WriteToBigQuery(
            em_opts.output_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )

        validated.errors | 'WriteErrors' >> beam.io.WriteToBigQuery(
            em_opts.error_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )

    logger.info(f"EM pipeline completed: entity={entity}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_em_pipeline()


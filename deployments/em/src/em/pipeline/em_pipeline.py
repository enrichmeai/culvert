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
  4. Validate each record using SCHEMA-DRIVEN validation
  5. Write valid records to BigQuery ODP table
  6. Write error records to error table
  7. Update job_control table
  8. Archive source files

Library Components Used:
  - gcp_pipeline_builder.file_management.HDRTRLParser
  - gcp_pipeline_builder.pipelines.beam.transforms.ParseCsvLine
  - gcp_pipeline_builder.pipelines.beam.transforms.SchemaValidateRecordDoFn
  - gcp_pipeline_builder.job_control.JobControlRepository

Entities:
  - customers → odp_em.customers
  - accounts → odp_em.accounts
  - decision → odp_em.decision

Usage:
  python em_pipeline.py --entity=customers --input_pattern=gs://bucket/em/customers/*.csv
"""

import logging
from datetime import datetime
from typing import Dict, Any, Iterator

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - schema-driven validation
from gcp_pipeline_builder.file_management import HDRTRLParser
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_builder.pipelines.beam.transforms import ParseCsvLine, SchemaValidateRecordDoFn

# EM-specific imports - ONLY configuration and schemas
from em.config import SYSTEM_ID
from em.schema import EMCustomerSchema, EMAccountSchema, EMDecisionSchema, EM_SCHEMAS

logger = logging.getLogger(__name__)


# Entity configuration - maps entity name to schema
EM_ENTITY_CONFIG = {
    "customers": {
        "schema": EMCustomerSchema,
        "output_table": "odp_em.customers",
        "error_table": "odp_em.customers_errors",
    },
    "accounts": {
        "schema": EMAccountSchema,
        "output_table": "odp_em.accounts",
        "error_table": "odp_em.accounts_errors",
    },
    "decision": {
        "schema": EMDecisionSchema,
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
    """
    Run the EM ODP load pipeline.

    Uses schema-driven validation - no custom validation code needed.
    The schema defines required fields, allowed values, max lengths, types.
    """
    options = EMPipelineOptions(argv)
    em_opts = options.view_as(EMPipelineOptions)

    entity = em_opts.entity
    config = EM_ENTITY_CONFIG[entity]
    schema = config["schema"]
    run_id = em_opts.run_id or f"em_{entity}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Starting EM pipeline: entity={entity}, run_id={run_id}")
    logger.info(f"Using schema-driven validation for {schema.entity_name}")

    with beam.Pipeline(options=options) as p:
        # Read files
        lines = p | 'ReadFiles' >> beam.io.ReadFromText(em_opts.input_pattern)

        # Parse CSV - headers from schema, uses library ParseCsvLine
        records = lines | 'ParseCSV' >> beam.ParDo(
            ParseCsvLine(
                headers=schema.get_csv_headers(),
                skip_hdr_trl=True,
                hdr_prefix="HDR|",
                trl_prefix="TRL|"
            )
        )

        # Validate using SCHEMA-DRIVEN validation from library
        # No custom validation code - schema defines everything!
        validated = records | 'Validate' >> beam.ParDo(
            SchemaValidateRecordDoFn(schema=schema)
        ).with_outputs('invalid', main='valid')

        # Add audit columns
        audited = validated.valid | 'AddAudit' >> beam.ParDo(
            AddAuditColumnsDoFn(run_id, em_opts.input_pattern,
                               datetime.utcnow().strftime('%Y-%m-%d'))
        )

        # Write to BigQuery - schema from EntitySchema
        audited | 'WriteODP' >> beam.io.WriteToBigQuery(
            em_opts.output_table,
            schema={'fields': schema.to_bq_schema()},
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
        )

        validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(
            em_opts.error_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )

    logger.info(f"EM pipeline completed: entity={entity}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_em_pipeline()

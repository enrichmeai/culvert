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
  4. Validate each record using SCHEMA-DRIVEN validation
  5. Write valid records to BigQuery ODP table
  6. Write error records to error table
  7. Update job_control table with metrics
  8. Archive source files

Library Components Used:
  - gcp_pipeline_builder.utilities.configure_structured_logging (JSON logging)
  - gcp_pipeline_builder.monitoring.MigrationMetrics (standardized metrics)
  - gcp_pipeline_builder.pipelines.beam.transforms.ParseCsvLine
  - gcp_pipeline_builder.pipelines.beam.transforms.SchemaValidateRecordDoFn

Entities:
  - applications → odp_loa.applications

Note: Unlike EM (which waits for 3 entities), LOA immediately triggers
      FDP transformation after ODP load (single entity, no dependency wait).

Usage:
  python loa_pipeline.py --entity=applications --input_pattern=gs://bucket/loa/applications/*.csv
"""

from datetime import datetime
from typing import Dict, Any, Iterator

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - structured logging and metrics
from gcp_pipeline_builder.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_builder.monitoring import MigrationMetrics

# Library imports - schema-driven validation
from gcp_pipeline_builder.file_management import HDRTRLParser
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_builder.pipelines.beam.transforms import ParseCsvLine, SchemaValidateRecordDoFn

# LOA-specific imports - ONLY configuration and schemas
from loa.config import SYSTEM_ID
from loa.schema import LOAApplicationsSchema, LOA_SCHEMAS


# Entity configuration - maps entity name to schema
LOA_ENTITY_CONFIG = {
    "applications": {
        "schema": LOAApplicationsSchema,
        "output_table": "odp_loa.applications",
        "error_table": "odp_loa.applications_errors",
    },
}


class LOAPipelineOptions(PipelineOptions):
    """LOA Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument('--entity', type=str, required=True,
                          choices=['applications'],
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


def run_loa_pipeline(argv=None):
    """
    Run the LOA ODP load pipeline.

    Uses:
    - Structured JSON logging for Cloud Logging
    - MigrationMetrics for standardized metrics
    - Schema-driven validation - no custom validation code needed

    After completion, triggers FDP transformation immediately
    (no dependency wait - single entity).
    """
    options = LOAPipelineOptions(argv)
    loa_opts = options.view_as(LOAPipelineOptions)

    entity = loa_opts.entity
    config = LOA_ENTITY_CONFIG[entity]
    schema = config["schema"]
    run_id = loa_opts.run_id or generate_run_id(f"loa_{entity}")

    # Configure structured JSON logging
    logger = configure_structured_logging(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        logger_name="loa_pipeline"
    )

    # Initialize migration metrics
    metrics = MigrationMetrics(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity
    )

    logger.info("Pipeline starting",
                input_pattern=loa_opts.input_pattern,
                output_table=loa_opts.output_table,
                note="Single entity - immediate FDP trigger after ODP load")

    try:
        with beam.Pipeline(options=options) as p:
            # Read files
            lines = p | 'ReadFiles' >> beam.io.ReadFromText(loa_opts.input_pattern)

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
            validated = records | 'Validate' >> beam.ParDo(
                SchemaValidateRecordDoFn(schema=schema)
            ).with_outputs('invalid', main='valid')

            # Add audit columns
            audited = validated.valid | 'AddAudit' >> beam.ParDo(
                AddAuditColumnsDoFn(run_id, loa_opts.input_pattern,
                                   datetime.utcnow().strftime('%Y-%m-%d'))
            )

            # Write to BigQuery - schema from EntitySchema
            audited | 'WriteODP' >> beam.io.WriteToBigQuery(
                loa_opts.output_table,
                schema={'fields': schema.to_bq_schema()},
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )

            validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(
                loa_opts.error_table,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
            )

        # Log success with metrics summary
        summary = metrics.get_summary()
        logger.info("Pipeline completed successfully",
                    duration_seconds=summary['duration'],
                    counts=summary['counts'],
                    rates=summary['rates'],
                    note="FDP transformation can be triggered immediately")

    except Exception as e:
        logger.error("Pipeline failed", error=str(e), exception_type=type(e).__name__)
        raise


if __name__ == '__main__':
    run_loa_pipeline()


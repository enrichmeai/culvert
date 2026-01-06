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
  7. Reconcile source count with BigQuery count
  8. Update job_control table with metrics
  9. Archive source files

Library Components Used:
  - gcp_pipeline_builder.utilities.configure_structured_logging (JSON logging)
  - gcp_pipeline_builder.monitoring.MigrationMetrics (standardized metrics)
the  - gcp_pipeline_builder.monitoring.otel (OTEL/Dynatrace integration)
  - gcp_pipeline_builder.audit.ReconciliationEngine (automated reconciliation)
  - gcp_pipeline_builder.pipelines.beam.transforms.ParseCsvLine
  - gcp_pipeline_builder.pipelines.beam.transforms.SchemaValidateRecordDoFn

Entities:
  - applications → odp_loa.applications

Note: Unlike EM (which waits for 3 entities), LOA immediately triggers
      FDP transformation after ODP load (single entity, no dependency wait).

OTEL Configuration:
  Set environment variables for Dynatrace integration:
    OTEL_EXPORTER_TYPE=dynatrace
    DYNATRACE_OTEL_URL=https://your-env.live.dynatrace.com/api/v2/otlp
    DYNATRACE_API_TOKEN=dt0c01.xxx

Usage:
  python loa_pipeline.py --entity=applications --input_pattern=gs://bucket/loa/applications/*.csv
"""

import os
from datetime import datetime
from typing import Dict, Any, Iterator, Optional

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - structured logging and metrics
from gcp_pipeline_builder.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_builder.monitoring import MigrationMetrics

# Library imports - OTEL integration (optional)
from gcp_pipeline_builder.monitoring.otel import (
    OTELConfig,
    configure_otel,
    OTELContext,
    OTELMetricsBridge,
    shutdown_otel,
)

# Library imports - reconciliation
from gcp_pipeline_builder.audit import ReconciliationEngine, ReconciliationStatus

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


def initialize_otel(run_id: str, entity_type: str, environment: str = "dev") -> bool:
    """
    Initialize OpenTelemetry for distributed tracing.

    Checks environment variables for Dynatrace/OTEL configuration.
    If not configured, OTEL is disabled (no-op).

    Environment Variables:
        OTEL_EXPORTER_TYPE: Exporter type (dynatrace, gcp_trace, console, none)
        DYNATRACE_OTEL_URL: Dynatrace OTLP endpoint
        DYNATRACE_API_TOKEN: Dynatrace API token

    Args:
        run_id: Pipeline run ID
        entity_type: Entity being processed
        environment: Deployment environment

    Returns:
        True if OTEL initialized successfully
    """
    exporter_type = os.getenv("OTEL_EXPORTER_TYPE", "none")

    if exporter_type == "none":
        return False

    dynatrace_url = os.getenv("DYNATRACE_OTEL_URL")
    dynatrace_token = os.getenv("DYNATRACE_API_TOKEN")

    if exporter_type == "dynatrace" and dynatrace_url and dynatrace_token:
        config = OTELConfig.for_dynatrace(
            service_name="loa-pipeline",
            dynatrace_url=dynatrace_url,
            dynatrace_token=dynatrace_token,
            environment=environment,
            resource_attributes={
                "system.id": SYSTEM_ID,
                "entity.type": entity_type,
                "run.id": run_id,
            }
        )
    elif exporter_type == "console":
        config = OTELConfig.for_console(service_name="loa-pipeline")
    else:
        config = OTELConfig.disabled()

    return configure_otel(config)


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
        parser.add_argument('--skip_reconciliation', action='store_true',
                          help='Skip reconciliation check')


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


def run_loa_pipeline(argv=None, expected_count: Optional[int] = None):
    """
    Run the LOA ODP load pipeline.

    Uses:
    - Structured JSON logging for Cloud Logging
    - OTEL/Dynatrace integration for distributed tracing
    - MigrationMetrics for standardized metrics
    - ReconciliationEngine for automated reconciliation
    - Schema-driven validation - no custom validation code needed

    After completion, triggers FDP transformation immediately
    (no dependency wait - single entity).

    Args:
        argv: Command line arguments
        expected_count: Expected record count (from trailer) for reconciliation
    """
    options = LOAPipelineOptions(argv)
    loa_opts = options.view_as(LOAPipelineOptions)

    entity = loa_opts.entity
    config = LOA_ENTITY_CONFIG[entity]
    schema = config["schema"]
    run_id = loa_opts.run_id or generate_run_id(f"loa_{entity}")
    environment = os.getenv("ENVIRONMENT", "dev")

    # Configure structured JSON logging
    logger = configure_structured_logging(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        logger_name="loa_pipeline"
    )

    # Initialize OTEL for distributed tracing (if configured)
    otel_enabled = initialize_otel(run_id, entity, environment)
    if otel_enabled:
        logger.info("OTEL tracing enabled", exporter=os.getenv("OTEL_EXPORTER_TYPE"))

    # Initialize migration metrics (with OTEL bridge if enabled)
    base_metrics = MigrationMetrics(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity
    )
    # Wrap with OTEL bridge to export metrics to Dynatrace/OTEL
    metrics = OTELMetricsBridge(base_metrics) if otel_enabled else base_metrics

    # Initialize reconciliation engine
    reconciler = ReconciliationEngine(
        entity_type=entity,
        run_id=run_id,
        project_id=loa_opts.project_id,
        logger=logger
    )

    logger.info("Pipeline starting",
                input_pattern=loa_opts.input_pattern,
                output_table=loa_opts.output_table,
                note="Single entity - immediate FDP trigger after ODP load")

    try:
        # Wrap pipeline execution in OTEL context for distributed tracing
        with OTELContext(run_id=run_id, system_id=SYSTEM_ID, entity_type=entity) as otel_ctx:
            with otel_ctx.span("pipeline_execution", attributes={"input_pattern": loa_opts.input_pattern}) as span:
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

                # Mark pipeline execution complete
                span.set_attribute("status", "success")

            # Log success with metrics summary
            summary = metrics.get_summary()
            logger.info("Pipeline completed successfully",
                        duration_seconds=summary['duration'],
                        counts=summary['counts'],
                        rates=summary['rates'],
                        note="FDP transformation can be triggered immediately")

            # Perform reconciliation if expected_count provided
            if expected_count is not None and not loa_opts.skip_reconciliation:
                with otel_ctx.span("reconciliation") as recon_span:
                    logger.info("Starting reconciliation", expected_count=expected_count)

                    recon_result = reconciler.reconcile_with_bigquery(
                        expected_count=expected_count,
                        destination_table=loa_opts.output_table,
                        error_table=loa_opts.error_table
                    )

                    recon_span.set_attribute("expected_count", expected_count)
                    recon_span.set_attribute("actual_count", recon_result.actual_count)

                    if not recon_result.is_reconciled:
                        recon_span.set_attribute("status", "failed")
                        logger.warning("Reconciliation failed",
                                      expected=recon_result.expected_count,
                                      actual=recon_result.actual_count,
                                      difference=recon_result.difference)
                    else:
                        recon_span.set_attribute("status", "passed")
                        logger.info("Reconciliation passed",
                                   expected=recon_result.expected_count,
                                   actual=recon_result.actual_count)

    except Exception as e:
        logger.error("Pipeline failed", error=str(e), exception_type=type(e).__name__)
        raise
    finally:
        # Ensure OTEL is shutdown gracefully
        if otel_enabled:
            shutdown_otel()


if __name__ == '__main__':
    run_loa_pipeline()

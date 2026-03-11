"""
Generic (Application A) - Apache Beam/Dataflow Pipeline
=======================================================

Purpose:
  Pipeline for loading Generic mainframe extracts to BigQuery ODP tables.
  Handles 3 entities: Customers, Accounts, Decision.

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
  - gcp_pipeline_core.utilities.configure_structured_logging (JSON logging)
  - gcp_pipeline_core.monitoring.MigrationMetrics (standardized metrics)
  - gcp_pipeline_core.monitoring.otel (OTEL/Dynatrace integration)
  - gcp_pipeline_core.audit.ReconciliationEngine (automated reconciliation)
  - gcp_pipeline_beam.pipelines.beam.transforms.ParseCsvLine
  - gcp_pipeline_beam.pipelines.beam.transforms.SchemaValidateRecordDoFn

Entities:
  - customers → odp_generic.customers
  - accounts → odp_generic.accounts
  - decision → odp_generic.decision

OTEL Configuration:
  Set environment variables for Dynatrace integration:
    OTEL_EXPORTER_TYPE=dynatrace
    DYNATRACE_OTEL_URL=https://your-env.live.dynatrace.com/api/v2/otlp
    DYNATRACE_API_TOKEN=dt0c01.xxx

Usage:
  python ingestion_pipeline.py --entity=customers --input_pattern=gs://bucket/generic/customers/*.csv
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Iterator, Optional

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - structured logging and metrics
from gcp_pipeline_core.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_core.monitoring import MigrationMetrics

# Library imports - OTEL integration (optional)
from gcp_pipeline_core.monitoring.otel import (
    OTELConfig,
    configure_otel,
    OTELContext,
    OTELMetricsBridge,
    shutdown_otel,
)

# Library imports - reconciliation
from gcp_pipeline_core.audit import ReconciliationEngine, ReconciliationStatus

# Library imports - base pipeline and components
from gcp_pipeline_beam.pipelines.base import BasePipeline, GCPPipelineOptions
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine, SchemaValidateRecordDoFn

# Generic-specific imports - ONLY configuration and schemas
from data_ingestion.config import SYSTEM_ID
from data_ingestion.schema import EMCustomerSchema, EMAccountSchema, EMDecisionSchema, EM_SCHEMAS


# Entity configuration - maps entity name to schema
EM_ENTITY_CONFIG = {
    "customers": {
        "schema": EMCustomerSchema,
        "output_table": "odp_generic.customers",
        "error_table": "odp_generic.customers_errors",
    },
    "accounts": {
        "schema": EMAccountSchema,
        "output_table": "odp_generic.accounts",
        "error_table": "odp_generic.accounts_errors",
    },
    "decision": {
        "schema": EMDecisionSchema,
        "output_table": "odp_generic.decision",
        "error_table": "odp_generic.decision_errors",
    },
}


class EMPipeline(BasePipeline):
    """
    Generic (Application A) ODP Load Pipeline.
    Refactored to use library BasePipeline for enhanced maturity features.
    """

    def __init__(self, options, config, entity_schema):
        super().__init__(options=options, config=config)
        self.entity_schema = entity_schema

    def build(self, pipeline: beam.Pipeline):
        """Build the Generic pipeline logic."""
        gcp_opts = self.options.view_as(GCPPipelineOptions)

        # Read files
        lines = pipeline | 'ReadFiles' >> beam.io.ReadFromText(gcp_opts.input_pattern)

        # Parse CSV - headers from schema, uses library ParseCsvLine
        records = lines | 'ParseCSV' >> beam.ParDo(
            ParseCsvLine(
                field_names=self.entity_schema.get_csv_headers(),
                skip_hdr_trl=True,
                hdr_prefix="HDR|",
                trl_prefix="TRL|"
            )
        )

        # Validate using SCHEMA-DRIVEN validation from library
        validated = records | 'Validate' >> beam.ParDo(
            SchemaValidateRecordDoFn(schema=self.entity_schema)
        ).with_outputs('invalid', main='valid')

        # Add audit columns
        audited = validated.valid | 'AddAudit' >> beam.ParDo(
            AddAuditColumnsDoFn(
                self.run_id,
                gcp_opts.input_pattern,
                datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
            )
        )

        # Write to BigQuery - using BasePipeline helper with DLQ support
        # Valid records
        self.write_to_bigquery(
            audited,
            gcp_opts.output_table,
            schema={'fields': self.entity_schema.to_bq_schema()},
            dlq_path=f"gs://{self.config.get('gcp_project_id')}-dlq/generic/{self.run_id}/valid_failures"
        )

        # Invalid records (Validation errors)
        self.write_to_bigquery(
            validated.invalid,
            gcp_opts.error_table,
            schema=None, # Use auto-detection for error table or specific schema
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            dlq_path=f"gs://{self.config.get('gcp_project_id')}-dlq/generic/{self.run_id}/validation_failures"
        )


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
            service_name="generic-pipeline",
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
        config = OTELConfig.for_console(service_name="generic-pipeline")
    else:
        config = OTELConfig.disabled()

    return configure_otel(config)


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
        record['_processed_at'] = datetime.now(tz=timezone.utc).isoformat()
        record['_extract_date'] = self.extract_date
        yield record


def run_ingestion_pipeline(argv=None, expected_count: Optional[int] = None):
    """
    Run the Generic ODP load pipeline.
    Updated to use EMPipeline class which inherits from BasePipeline.
    """
    # Parse entity before Beam options to avoid PipelineOptions subclass conflicts
    import argparse as _ap
    _pre = _ap.ArgumentParser(add_help=False)
    _pre.add_argument('--entity', choices=['customers', 'accounts', 'decision'])
    _pre_args, _ = _pre.parse_known_args(argv)

    options = GCPPipelineOptions(argv)
    gcp_opts = options.view_as(GCPPipelineOptions)

    entity = _pre_args.entity
    config_entry = EM_ENTITY_CONFIG[entity]
    schema = config_entry["schema"]
    run_id = gcp_opts.run_id or generate_run_id(f"generic_{entity}")
    environment = os.getenv("ENVIRONMENT", "dev")

    # Configure structured JSON logging
    logger = configure_structured_logging(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        logger_name="ingestion_pipeline"
    )

    # Prepare configuration for BasePipeline
    pipeline_config = {
        'run_id': gcp_opts.run_id,
        'pipeline_name': f"generic_{entity}_load",
        'entity_type': entity,
        'gcp_project_id': gcp_opts.gcp_project,
        'source_file': gcp_opts.input_pattern
    }

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
        project_id=gcp_opts.gcp_project,
        logger=logger
    )

    logger.info("Pipeline starting",
                input_pattern=gcp_opts.input_pattern,
                output_table=gcp_opts.output_table)

    try:
        # Wrap pipeline execution in OTEL context for distributed tracing
        with OTELContext(run_id=run_id, system_id=SYSTEM_ID, entity_type=entity) as otel_ctx:
            with otel_ctx.span("pipeline_execution", attributes={"input_pattern": gcp_opts.input_pattern}) as span:
                # Instantiate and run the library-based pipeline
                pipeline = EMPipeline(options, pipeline_config, schema)
                pipeline.run()

                # Mark pipeline execution complete
                span.set_attribute("status", "success")

            # Log success with metrics summary
            summary = metrics.get_summary()
            logger.info("Pipeline completed successfully",
                        duration_seconds=summary['duration'],
                        counts=summary['counts'],
                        rates=summary['rates'])

            # Perform reconciliation if expected_count provided
            if expected_count is not None and not gcp_opts.skip_reconciliation:
                with otel_ctx.span("reconciliation") as recon_span:
                    logger.info("Starting reconciliation", expected_count=expected_count)

                    recon_result = reconciler.reconcile_with_bigquery(
                        expected_count=expected_count,
                        destination_table=generic_opts.output_table,
                        error_table=generic_opts.error_table
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
    run_ingestion_pipeline()

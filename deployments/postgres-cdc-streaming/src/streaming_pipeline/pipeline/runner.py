"""
Streaming CDC Pipeline Runner

Real-time CDC streaming: PostgreSQL → Kafka → Beam (Streaming) → ODP → FDP

Uses gcp-pipeline-framework libraries:
  - GCPPipelineOptions: Standardised CLI options
  - JobControlRepository: Track streaming job in job_control.pipeline_jobs
  - AuditTrail / AuditPublisher: Publish audit events to Pub/Sub
  - ErrorHandler: Classify and handle errors with retry strategies
  - MetricsCollector: Track processing counters

This pipeline demonstrates:
1. Reading CDC events from Pub/Sub (Debezium format via Kafka Connect)
2. Parsing and validating CDC records
3. Streaming inserts to BigQuery ODP
4. Windowed aggregation and transformation to FDP
5. Full audit trail with run_id across the stream
"""

import argparse
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Dict, Any

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition

# Framework imports
from gcp_pipeline_beam.pipelines.base.options import GCPPipelineOptions
from gcp_pipeline_core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)
from gcp_pipeline_core.audit.trail import AuditTrail
from gcp_pipeline_core.audit.publisher import AuditPublisher
from gcp_pipeline_core.error_handling.handler import ErrorHandler
from gcp_pipeline_core.error_handling.types import ErrorSeverity, ErrorCategory
from gcp_pipeline_core.monitoring.metrics import MetricsCollector

# Local transforms
from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn
from streaming_pipeline.pipeline.transforms import (
    TransformToODPDoFn,
    TransformToFDPDoFn,
    AddStreamingAuditDoFn,
)
from streaming_pipeline.pipeline.windows import StreamingWindowStrategies


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamingCDCOptions(PipelineOptions):
    """Custom pipeline options for streaming CDC."""

    @classmethod
    def _add_argparse_args(cls, parser):
        # Kafka configuration
        parser.add_argument(
            "--kafka_bootstrap_servers",
            required=True,
            help="Kafka bootstrap servers (comma-separated)",
        )
        parser.add_argument(
            "--kafka_topic",
            required=True,
            help="Kafka topic to consume CDC events from",
        )
        parser.add_argument(
            "--kafka_consumer_group",
            default="beam-streaming-cdc",
            help="Kafka consumer group ID",
        )

        # BigQuery configuration
        parser.add_argument(
            "--bq_project",
            required=True,
            help="BigQuery project ID",
        )
        parser.add_argument(
            "--odp_dataset",
            default="odp_streaming",
            help="BigQuery dataset for ODP tables",
        )
        parser.add_argument(
            "--fdp_dataset",
            default="fdp_streaming",
            help="BigQuery dataset for FDP tables",
        )
        parser.add_argument(
            "--entity_name",
            required=True,
            help="Entity name (e.g., customers, accounts)",
        )

        # Windowing configuration
        parser.add_argument(
            "--window_size_seconds",
            type=int,
            default=60,
            help="Window size in seconds for FDP aggregation",
        )
        parser.add_argument(
            "--early_firing_seconds",
            type=int,
            default=10,
            help="Early firing interval in seconds",
        )

        # Run configuration
        parser.add_argument(
            "--run_id",
            default=None,
            help="Run ID for audit trail (auto-generated if not provided)",
        )


def build_odp_schema():
    """Build BigQuery schema for ODP table."""
    return {
        "fields": [
            {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "name", "type": "STRING", "mode": "NULLABLE"},
            {"name": "email", "type": "STRING", "mode": "NULLABLE"},
            {"name": "status", "type": "STRING", "mode": "NULLABLE"},
            {"name": "ssn", "type": "STRING", "mode": "NULLABLE"},
            {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "updated_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
            # CDC metadata
            {"name": "_cdc_operation", "type": "STRING", "mode": "REQUIRED"},
            {"name": "_cdc_event_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "_cdc_source_table", "type": "STRING", "mode": "NULLABLE"},
            # Audit columns
            {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "_processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        ]
    }


def build_fdp_schema():
    """Build BigQuery schema for FDP table."""
    return {
        "fields": [
            {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "full_name", "type": "STRING", "mode": "NULLABLE"},
            {"name": "email_domain", "type": "STRING", "mode": "NULLABLE"},
            {"name": "status", "type": "STRING", "mode": "NULLABLE"},
            {"name": "ssn_masked", "type": "STRING", "mode": "NULLABLE"},
            # Window metadata
            {"name": "window_start", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "window_end", "type": "TIMESTAMP", "mode": "REQUIRED"},
            # CDC aggregation
            {"name": "cdc_operation", "type": "STRING", "mode": "NULLABLE"},
            {"name": "cdc_event_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
            # Audit columns
            {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "_fdp_processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        ]
    }


def run_streaming_pipeline():
    """
    Main entry point for the streaming CDC pipeline.

    Integrates with gcp-pipeline-framework:
    - Job control: registers streaming job in pipeline_jobs
    - Error handling: classifies errors with retry strategies
    - Audit trail: publishes events to Pub/Sub topic
    - Metrics: tracks processing counts

    Flow:
    1. Read from Pub/Sub (CDC events from Kafka Connect)
    2. Parse Debezium CDC format
    3. Transform and write to ODP (immediate streaming inserts)
    4. Window and aggregate
    5. Transform and write to FDP (windowed streaming inserts)
    """
    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args()

    options = PipelineOptions(pipeline_args)
    streaming_options = options.view_as(StreamingCDCOptions)
    standard_options = options.view_as(StandardOptions)

    # Enable streaming mode
    standard_options.streaming = True

    # Generate run_id if not provided
    run_id = (streaming_options.run_id
              or f"stream_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}")
    project_id = streaming_options.bq_project
    entity_name = streaming_options.entity_name

    logger.info("Starting streaming CDC pipeline")
    logger.info("  Kafka topic: %s", streaming_options.kafka_topic)
    logger.info("  Entity: %s", entity_name)
    logger.info("  Run ID: %s", run_id)

    # --- Framework: Job Control ---
    job_repo = JobControlRepository(project_id=project_id)
    job = PipelineJob(
        run_id=run_id,
        system_id='postgres_cdc',
        entity_type=entity_name,
        extract_date=date.today(),
        source_files=[f"pubsub://{streaming_options.kafka_topic}"],
    )
    job_repo.create_job(job)
    job_repo.update_status(run_id, JobStatus.RUNNING)

    # --- Framework: Error Handler ---
    error_handler = ErrorHandler(
        pipeline_name='postgres-cdc-streaming',
        run_id=run_id,
    )

    # --- Framework: Metrics ---
    metrics = MetricsCollector(
        pipeline_name='postgres-cdc-streaming',
        run_id=run_id,
    )

    # --- Framework: Audit Trail ---
    try:
        audit_publisher = AuditPublisher(
            project_id=project_id,
            topic_name='generic-pipeline-events',
        )
        audit_trail = AuditTrail(
            run_id=run_id,
            pipeline_name='postgres-cdc-streaming',
            entity_type=entity_name,
            publisher=audit_publisher,
        )
        audit_trail.record_processing_start(
            source_file=f"pubsub://{streaming_options.kafka_topic}")
    except Exception as audit_err:
        logger.warning("Audit trail init failed (non-fatal): %s", audit_err)
        audit_trail = None

    try:
        with beam.Pipeline(options=options) as p:
            # Step 1: Read CDC events
            cdc_events = (
                p
                | "ReadFromPubSub" >> beam.io.ReadFromPubSub(
                    topic=f"projects/{project_id}/topics/{streaming_options.kafka_topic}",
                    with_attributes=True,
                )
                | "ExtractMessage" >> beam.Map(lambda msg: msg.data.decode("utf-8"))
            )

            # Step 2: Parse CDC events (Debezium format)
            parsed_records = (
                cdc_events
                | "ParseCDCEvent" >> beam.ParDo(ParseCDCEventDoFn())
                | "FilterValid" >> beam.Filter(lambda r: r is not None)
            )

            # Step 3: Transform to ODP and add audit columns
            odp_records = (
                parsed_records
                | "TransformToODP" >> beam.ParDo(TransformToODPDoFn())
                | "AddAuditColumns" >> beam.ParDo(AddStreamingAuditDoFn(run_id=run_id))
            )

            # Step 4: Write to ODP (streaming inserts)
            odp_table = f"{project_id}:{streaming_options.odp_dataset}.{entity_name}"
            odp_records | "WriteToODP" >> WriteToBigQuery(
                table=odp_table,
                schema=build_odp_schema(),
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                method="STREAMING_INSERTS",
            )

            # Step 5: Apply windowing for FDP aggregation
            window_strategy = StreamingWindowStrategies.fixed_with_early_firing(
                window_size_seconds=streaming_options.window_size_seconds,
                early_firing_seconds=streaming_options.early_firing_seconds,
                allowed_lateness_seconds=300,
            )
            windowed_records = (
                odp_records
                | "ApplyWindow" >> beam.WindowInto(
                    window_strategy["window"],
                    **window_strategy["kwargs"],
                )
            )

            # Step 6: Transform to FDP (within window)
            fdp_records = (
                windowed_records
                | "TransformToFDP" >> beam.ParDo(TransformToFDPDoFn(mask_pii=True))
            )

            # Step 7: Write to FDP
            fdp_table = f"{project_id}:{streaming_options.fdp_dataset}.{entity_name}_realtime"
            fdp_records | "WriteToFDP" >> WriteToBigQuery(
                table=fdp_table,
                schema=build_fdp_schema(),
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                method="STREAMING_INSERTS",
            )

        # --- Success ---
        job_repo.update_status(run_id, JobStatus.SUCCESS)
        metrics.increment('pipeline_runs_success')
        if audit_trail:
            try:
                audit_trail.record_processing_end(success=True)
            except Exception:
                pass
        logger.info("Streaming pipeline completed — run_id=%s", run_id)

    except Exception as exc:
        # --- Failure: classify and record ---
        error = error_handler.handle_exception(
            exc,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.INTEGRATION,
            source_file=f"pubsub://{streaming_options.kafka_topic}",
        )
        job_repo.mark_failed(
            run_id=run_id,
            error_code=error.error_type,
            error_message=str(exc)[:500],
            failure_stage=FailureStage.ODP_LOAD,
        )
        metrics.increment('pipeline_runs_failed')
        if audit_trail:
            try:
                audit_trail.record_processing_end(success=False)
            except Exception:
                pass
        logger.error("Streaming pipeline failed — run_id=%s: %s", run_id, exc)
        raise


if __name__ == "__main__":
    run_streaming_pipeline()

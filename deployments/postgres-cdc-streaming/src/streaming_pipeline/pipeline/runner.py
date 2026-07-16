"""
Streaming CDC Pipeline Runner

Real-time CDC streaming: PostgreSQL → Kafka → Beam (Streaming) → ODP → FDP

Built on Culvert (`culvert[gcp]` on PyPI):
  - PipelineJob / JobStatus / FailureStage: the job-control types
    (data_pipeline_core.job_control_api); writes go through the
    deployment-local BigQueryJobControlRepository, which implements the
    JobControlRepository Protocol's write path.
  - AuditRecord: published at start/end via the deployment-local
    PubSubAuditPublisher (implements the AuditEventPublisher Protocol).
  - StageMetrics + CloudMonitoringMetricsHook: launcher-side run metrics.

This pipeline demonstrates:
1. Reading CDC events from Pub/Sub (Debezium format via Kafka Connect)
2. Parsing and validating CDC records
3. Streaming inserts to BigQuery ODP
4. Windowed aggregation and transformation to FDP
5. Full audit trail with run_id across the stream
"""

import argparse
import logging
import time
import uuid
from datetime import date, datetime, timezone

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition

# Culvert framework imports
from data_pipeline_core.audit.records import AuditRecord
from data_pipeline_core.contracts.stage_metrics import StageMetrics
from data_pipeline_core.job_control_api import (
    FailureStage,
    JobStatus,
    PipelineJob,
)

# Local adapters (implement the Culvert Protocols at the deployment seam)
from streaming_pipeline.pipeline.audit import PubSubAuditPublisher
from streaming_pipeline.pipeline.job_control import BigQueryJobControlRepository

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

PIPELINE_NAME = "postgres-cdc-streaming"


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


def _audit_record(run_id: str, entity_name: str, source: str, *,
                  success: bool, duration_seconds: float,
                  event: str) -> AuditRecord:
    return AuditRecord(
        run_id=run_id,
        pipeline_name=PIPELINE_NAME,
        entity_type=entity_name,
        source_file=source,
        record_count=0,  # streaming: per-record counts live in the ODP audit columns
        processed_timestamp=datetime.now(timezone.utc),
        processing_duration_seconds=duration_seconds,
        success=success,
        metadata={"event": event},
    )


def _finish_run(job_repo, audit, project_id: str, run_id: str,
                entity_name: str, source: str, started: float, *,
                error: Exception | None) -> None:
    """Shared success/failure epilogue: job status, metrics, audit end."""
    duration = time.monotonic() - started
    if error is None:
        job_repo.update_status(run_id, JobStatus.SUCCEEDED)
    else:
        job_repo.mark_failed(
            run_id=run_id,
            error_code=type(error).__name__,
            error_message=str(error)[:500],
            failure_stage=FailureStage.LOAD,
        )
    _emit_run_metrics(project_id, run_id, duration_seconds=duration,
                      error_count=0 if error is None else 1)
    if audit:
        try:
            audit.publish(_audit_record(
                run_id, entity_name, source,
                success=error is None, duration_seconds=duration,
                event="processing_end"))
            audit.flush()
        except Exception:
            pass


def _emit_run_metrics(project_id: str, run_id: str, *,
                      duration_seconds: float, error_count: int) -> None:
    """Launcher-side run metrics via the Culvert monitoring hook.

    The hook swallows emission errors by design (resilience contract),
    so this can never fail the pipeline.
    """
    from google.cloud import monitoring_v3
    from data_pipeline_gcp_observability import CloudMonitoringMetricsHook

    hook = CloudMonitoringMetricsHook(
        monitoring_v3.MetricServiceClient(), project_id)
    hook.record_stage_metrics(StageMetrics(
        pipeline_id=PIPELINE_NAME,
        run_id=run_id,
        stage_name="streaming_run",
        rows_processed=0,  # streaming: row counts are windowed, not per-run
        stage_latency_ms=duration_seconds * 1000.0,
        error_count=error_count,
    ))


def run_streaming_pipeline():
    """
    Main entry point for the streaming CDC pipeline.

    Culvert integration:
    - Job control: registers the streaming job in job_control.pipeline_jobs
    - Audit trail: publishes AuditRecords to the pipeline-events topic
    - Metrics: emits launcher-side StageMetrics to Cloud Monitoring

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
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = (streaming_options.run_id
              or f"stream_{stamp}_{uuid.uuid4().hex[:8]}")
    project_id = streaming_options.bq_project
    entity_name = streaming_options.entity_name
    source = f"pubsub://{streaming_options.kafka_topic}"
    started = time.monotonic()

    logger.info("Starting streaming CDC pipeline")
    logger.info("  Kafka topic: %s", streaming_options.kafka_topic)
    logger.info("  Entity: %s", entity_name)
    logger.info("  Run ID: %s", run_id)

    # --- Culvert: Job Control ---
    job_repo = BigQueryJobControlRepository(project_id=project_id)
    job_repo.create_job(PipelineJob(
        run_id=run_id,
        system_id="postgres_cdc",
        pipeline_name=PIPELINE_NAME,
        extract_date=date.today(),
        status=JobStatus.CREATED,
        entity_type=entity_name,
        source_file=source,
    ))
    job_repo.update_status(run_id, JobStatus.RUNNING)

    # --- Culvert: Audit Trail ---
    try:
        audit = PubSubAuditPublisher(
            project_id=project_id,
            topic_name="generic-pipeline-events",
        )
        audit.publish(_audit_record(
            run_id, entity_name, source,
            success=True, duration_seconds=0.0, event="processing_start"))
        audit.flush()
    except Exception as audit_err:
        logger.warning("Audit trail init failed (non-fatal): %s", audit_err)
        audit = None

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
        _finish_run(job_repo, audit, project_id, run_id, entity_name,
                    source, started, error=None)
        logger.info("Streaming pipeline completed — run_id=%s", run_id)

    except Exception as exc:
        # --- Failure: record structured error context ---
        _finish_run(job_repo, audit, project_id, run_id, entity_name,
                    source, started, error=exc)
        logger.error("Streaming pipeline failed — run_id=%s: %s", run_id, exc)
        raise


if __name__ == "__main__":
    run_streaming_pipeline()

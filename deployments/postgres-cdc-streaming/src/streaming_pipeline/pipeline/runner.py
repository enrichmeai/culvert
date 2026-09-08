"""
Streaming CDC Pipeline Runner

Real-time CDC streaming: PostgreSQL → Kafka → Beam (Streaming) → ODP → FDP

Built on Culvert (`culvert[gcp]` on PyPI):
  - PipelineJob / JobStatus / FailureStage: the job-control types
    (data_pipeline_core.job_control_api); writes go through the library's
    BigQueryJobControlRepository (data_pipeline_gcp_bigquery), the single
    Python adapter for the JobControlRepository port. This deployment used
    to carry its own copy of that class - a second, unregistered
    implementation, which is the shadow model spine AD-14 forbids.
  - AuditEvent / EventKind: published at start/end via the
    deployment-local PubSubAuditPublisher (implements the
    AuditEventPublisher Protocol). Run-level events (RUN_START, RUN_END,
    ERROR_RAISED) fail the run if their append fails - spine AD-5.
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
from importlib import metadata

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition

# Culvert framework imports
from data_pipeline_core.audit.events import AuditEvent, EventKind
from data_pipeline_core.contracts.stage_metrics import StageMetrics
from data_pipeline_core.job_control_api import (
    FailureStage,
    JobStatus,
    PipelineJob,
)

from data_pipeline_gcp_bigquery import BigQueryJobControlRepository

# Local adapters (implement the Culvert Protocols at the deployment seam)
from streaming_pipeline.pipeline.audit import PubSubAuditPublisher

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

# Source system identifier: the same value the PipelineJob is registered under,
# so job control and the audit trail agree on one name for one system.
SYSTEM_ID = "postgres_cdc"

try:
    _VERSION = metadata.version("postgres-cdc-streaming")
except metadata.PackageNotFoundError:  # running from a source checkout
    _VERSION = "0.0.0+source"

# docs/CONTRACT.md section 4: emitter library name and version.
PRODUCER = f"{PIPELINE_NAME}@{_VERSION}"


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


def _audit_event(run_id: str, entity_name: str, kind: EventKind,
                 payload: dict) -> AuditEvent:
    """Build one docs/CONTRACT.md section 4 event.

    ``contract_version`` is stamped by AuditEvent itself, and the payload keys
    the kind requires are checked at construction - so a missing key fails
    here, not as a NULL in a query months later.
    """
    return AuditEvent(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity=entity_name,
        event_kind=kind,
        event_ts=datetime.now(timezone.utc),
        payload=payload,
        # Streaming has no HDR business date; the run's own date is the closest
        # honest answer, and it matches what the PipelineJob records.
        extract_date=date.today(),
        producer=PRODUCER,
    )


def _run_start_event(run_id: str, entity_name: str, source: str) -> AuditEvent:
    return _audit_event(run_id, entity_name, EventKind.RUN_START,
                        {"source_file": source})


def _run_end_event(run_id: str, entity_name: str,
                   duration_seconds: float) -> AuditEvent:
    return _audit_event(run_id, entity_name, EventKind.RUN_END, {
        # Streaming: per-record counts live in the ODP audit columns, so the
        # run-level total is not knowable here.
        "record_count": 0,
        "duration_seconds": duration_seconds,
    })


def _error_raised_event(run_id: str, entity_name: str, error: Exception,
                        duration_seconds: float) -> AuditEvent:
    return _audit_event(run_id, entity_name, EventKind.ERROR_RAISED, {
        "error_code": type(error).__name__,
        "error_message": str(error)[:500],
        # docs/CONTRACT.md section 9 allows validation / integration /
        # resource. Anything escaping the Beam pipeline here is a failure of an
        # external system (Pub/Sub, BigQuery, Dataflow) rather than of the data,
        # so "integration" is the honest bucket. Per-exception classification
        # needs a classifier this deployment does not have yet.
        "error_category": "integration",
        "duration_seconds": duration_seconds,
    })


def _finish_run(job_repo, audit, project_id: str, run_id: str,
                entity_name: str, started: float, *,
                error: Exception | None) -> None:
    """Shared success/failure epilogue: job status, metrics, audit end event.

    Takes no ``source``: RUN_START already recorded it, and neither RUN_END nor
    ERROR_RAISED carries it.
    """
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

    # No try/except here, deliberately. RUN_END and ERROR_RAISED are run-level
    # (spine AD-5): a failed append fails the run rather than reporting a
    # success that was never recorded. This block used to end in
    # `except Exception: pass`.
    if error is None:
        audit.publish(_run_end_event(run_id, entity_name, duration))
    else:
        audit.publish(_error_raised_event(run_id, entity_name, error, duration))
    audit.flush()


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
    - Audit trail: publishes AuditEvents to the pipeline-events topic
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
    # RUN_START is run-level (spine AD-5): if it cannot be recorded, the run
    # does not start. This used to log at WARN and continue with `audit = None`,
    # which is exactly how a pipeline runs for months with no audit trail while
    # looking healthy.
    audit = PubSubAuditPublisher(
        project_id=project_id,
        topic_name="generic-pipeline-events",
    )
    audit.publish(_run_start_event(run_id, entity_name, source))
    audit.flush()

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

    except Exception as exc:
        # --- Failure: record structured error context ---
        # Log the original cause FIRST. The ERROR_RAISED append below is
        # run-level and may now raise; if it does, the pipeline failure that
        # triggered it must already be on the record rather than being masked
        # by the audit failure.
        logger.error("Streaming pipeline failed - run_id=%s: %s", run_id, exc)
        _finish_run(job_repo, audit, project_id, run_id, entity_name,
                    started, error=exc)
        raise

    # --- Success ---
    # Deliberately OUTSIDE the try. RUN_END is run-level and may raise, and if
    # that raise were caught by the handler above the run would be marked
    # SUCCEEDED and then immediately mark_failed()'d, with a permanent
    # ERROR_RAISED row asserting a pipeline failure that never happened. That
    # is the late-ERROR_RAISED flip AD-3 exists to prevent. Out here, an audit
    # failure propagates as itself and job control keeps its true state.
    _finish_run(job_repo, audit, project_id, run_id, entity_name,
                started, error=None)
    logger.info("Streaming pipeline completed - run_id=%s", run_id)


if __name__ == "__main__":
    run_streaming_pipeline()

# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dags.py
"""
Generic Error Handling DAG

Proactive error monitoring and recovery — runs every 30 minutes:
  1. Scans job_control for FAILED jobs
  2. Categorises errors (CRITICAL / retryable / manual review)
  3. Auto-retries eligible ODP and FDP jobs
  4. Sends Dynatrace/ServiceNow alerts for critical failures
  5. Cleans up partial ODP loads before retry

Generated from system.yaml — all config baked in at build time.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import json
import logging
import os

from airflow import DAG
from airflow.models import Variable

try:
    from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
    from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
except ImportError:
    from airflow.operators.python import PythonOperator, BranchPythonOperator
    try:
        from airflow.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator

from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, FailureStage
from gcp_pipeline_core.error_handling import ErrorSeverity, ErrorCategory
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_core.monitoring.alerts import (
    AlertManager, DynatraceAlertBackend, ServiceNowAlertBackend,
    LoggingAlertBackend, CloudMonitoringBackend,
)
from gcp_pipeline_core.monitoring.types import AlertLevel
from gcp_pipeline_core.monitoring.metrics import MigrationMetrics
from gcp_pipeline_core.monitoring.otel.tracing import configure_otel, get_tracer, is_otel_initialized
from gcp_pipeline_core.monitoring.otel.config import OTELConfig
from gcp_pipeline_core.monitoring.otel.context import OTELContext
from gcp_pipeline_core.monitoring.otel.metrics_bridge import OTELMetricsBridge
from gcp_pipeline_core.audit.publisher import AuditPublisher
from gcp_pipeline_core.audit.records import AuditRecord
from gcp_pipeline_core.audit.lineage import DataLineageTracker
from gcp_pipeline_core.finops.tracker import BigQueryCostTracker

logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "GENERIC"
SYSTEM_NAME = "Generic"
FILE_PREFIX = "generic"
ENTITIES = ['customers', 'accounts', 'decision', 'applications']
FDP_MODELS = ['event_transaction_excess', 'portfolio_account_excess', 'portfolio_account_facility']
DAG_ID = "generic_error_handling_dag"
INGESTION_DAG_ID = "generic_ingestion_dag"
TRANSFORMATION_DAG_ID = "generic_transformation_dag"

# Infrastructure templates
ODP_DATASET_TEMPLATE = "odp_{system}"
ERROR_BUCKET_TEMPLATE = "{project_id}-{system}-{env}-error"

# Retry config (baked from system.yaml)
ODP_MAX_RETRIES = 3
ODP_CLEANUP_ON_RETRY = True
FDP_MAX_RETRIES = 2

# Error routing
RETRYABLE_STAGES = [
    FailureStage.ODP_LOAD.value,
    FailureStage.RECONCILIATION.value,
    FailureStage.FDP_MODEL.value,
    FailureStage.FDP_STAGING.value,
    FailureStage.FDP_TEST.value,
]
CRITICAL_STAGES = [
    FailureStage.FILE_DISCOVERY.value,
    FailureStage.FDP_DEPENDENCY.value,
]


def _resolve(template: str) -> str:
    project_id = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
    env = Variable.get("environment", default_var="int")
    return template.format(
        project_id=project_id, system=FILE_PREFIX, env=env, file_prefix=FILE_PREFIX,
    )


def _get_project_id() -> str:
    return Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))



# =============================================================================
# Observability helpers — Dynatrace + ServiceNow alerting + Audit publishing
# =============================================================================

def _get_alert_manager() -> AlertManager:
    """Create AlertManager with Dynatrace and ServiceNow backends if configured."""
    backends = [LoggingAlertBackend()]
    # Dynatrace Events API
    try:
        dt_url = Variable.get("dynatrace_environment_url")
        dt_token = Variable.get("dynatrace_api_token")
        if dt_url and dt_token:
            backends.append(DynatraceAlertBackend(
                environment_url=dt_url, api_token=dt_token,
            ))
    except Exception:
        pass  # Dynatrace not configured
    # ServiceNow incident creation
    try:
        snow_url = Variable.get("servicenow_instance_url")
        snow_user = Variable.get("servicenow_username")
        snow_pass = Variable.get("servicenow_password")
        if snow_url and snow_user:
            backends.append(ServiceNowAlertBackend(
                instance_url=snow_url,
                username=snow_user,
                password=snow_pass,
                assignment_group=Variable.get("servicenow_assignment_group", default_var=""),
            ))
    except Exception:
        pass  # ServiceNow not configured
    return AlertManager(alert_backends=backends)


def _send_failure_alert(dag_id: str, task_id: str, exception=None, metadata=None):
    """Send Slack + logging alert on task failure. Graceful no-op if Slack not configured."""
    try:
        alert_mgr = _get_alert_manager()
        error_msg = str(exception)[:500] if exception else "Unknown error"
        alert_mgr.create_alert(
            level=AlertLevel.CRITICAL,
            title=f"Pipeline Failure: {{dag_id}}",
            message=f"Task `{{task_id}}` failed: {{error_msg}}",
            source=dag_id,
            metadata=metadata or {{"task_id": task_id, "dag_id": dag_id}},
        )
    except Exception as e:
        logger.warning(f"Slack alert failed (non-fatal): {{e}}")


def _publish_audit(run_id, pipeline_name, entity, source_file,
                   record_count=0, duration_seconds=0.0, success=True,
                   error_count=0, metadata=None):
    """Publish audit record to Pub/Sub. Graceful no-op on failure."""
    try:
        project_id = _get_project_id()
        topic = Variable.get("audit_pubsub_topic", default_var="generic-pipeline-events")
        record = AuditRecord(
            run_id=run_id,
            pipeline_name=pipeline_name,
            entity_type=entity,
            source_file=source_file,
            record_count=record_count,
            processed_timestamp=datetime.now(tz=timezone.utc),
            processing_duration_seconds=duration_seconds,
            success=success,
            error_count=error_count,
            audit_hash="",
            metadata=metadata or {{}},
        )
        publisher = AuditPublisher(project_id=project_id, topic_name=topic)
        msg_id = publisher.publish(record)
        logger.info(f"Published audit record to {{topic}}: {{msg_id}}")
    except Exception as e:
        logger.warning(f"Audit publishing failed (non-fatal): {{e}}")


def _track_pipeline_cost(run_id: str, labels_filter: dict = None):
    """
    Track FinOps cost by querying INFORMATION_SCHEMA.JOBS for recent BQ jobs
    matching the run_id label, then store totals in job_control.

    Falls back gracefully if INFORMATION_SCHEMA is not accessible.
    """
    try:
        from google.cloud import bigquery as bq
        project_id = _get_project_id()
        client = bq.Client(project=project_id)

        # Query BQ jobs from last 24h that match our run_id label
        query = f"""
            SELECT
                SUM(total_bytes_billed) AS total_bytes_scanned,
                SUM(IFNULL(total_bytes_processed, 0)) AS total_bytes_written,
                COUNT(*) AS job_count
            FROM `region-europe-west2`.INFORMATION_SCHEMA.JOBS
            WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
              AND state = 'DONE'
              AND labels.run_id = @run_id
        """
        job_config = bq.QueryJobConfig(
            query_parameters=[
                bq.ScalarQueryParameter("run_id", "STRING", run_id),
            ]
        )
        results = list(client.query(query, job_config=job_config).result())

        if results and results[0].total_bytes_scanned:
            bytes_scanned = results[0].total_bytes_scanned or 0
            bytes_written = results[0].total_bytes_written or 0
            # BQ on-demand pricing: $6.25/TiB
            cost_usd = bytes_scanned * 6.25 / (1024 ** 4)

            repo = JobControlRepository(project_id=project_id)
            repo.update_cost_metrics(
                run_id=run_id,
                estimated_cost_usd=cost_usd,
                billed_bytes_scanned=bytes_scanned,
                billed_bytes_written=bytes_written,
            )
            logger.info(f"FinOps: {{run_id}} cost=${{cost_usd:.6f}}, "
                         f"scanned={{bytes_scanned:,}} bytes, "
                         f"written={{bytes_written:,}} bytes, "
                         f"jobs={{results[0].job_count}}")
        else:
            logger.info(f"FinOps: no BQ jobs found with label run_id={{run_id}}")
    except Exception as e:
        logger.warning(f"FinOps cost tracking failed (non-fatal): {{e}}")


def _publish_lineage(run_id, pipeline_name, entity, source_file,
                     record_count=0, duration_seconds=0.0, success=True,
                     error_count=0, metadata=None):
    """Generate and publish data lineage to Pub/Sub. Graceful no-op on failure."""
    try:
        record = AuditRecord(
            run_id=run_id,
            pipeline_name=pipeline_name,
            entity_type=entity,
            source_file=source_file,
            record_count=record_count,
            processed_timestamp=datetime.now(tz=timezone.utc),
            processing_duration_seconds=duration_seconds,
            success=success,
            error_count=error_count,
            audit_hash="",
            metadata=metadata or {{}},
        )
        lineage = DataLineageTracker.generate_data_lineage(record)
        logger.info(f"Data lineage: {{lineage}}")
        # Publish lineage alongside audit record
        project_id = _get_project_id()
        topic = Variable.get("audit_pubsub_topic", default_var="generic-pipeline-events")
        publisher = AuditPublisher(project_id=project_id, topic_name=topic)
        import json
        lineage_record = AuditRecord(
            run_id=run_id,
            pipeline_name=pipeline_name,
            entity_type=entity,
            source_file=source_file,
            record_count=record_count,
            processed_timestamp=datetime.now(tz=timezone.utc),
            processing_duration_seconds=duration_seconds,
            success=success,
            error_count=error_count,
            audit_hash="",
            metadata={{"lineage": lineage, **(metadata or {{}})}},
        )
        msg_id = publisher.publish(lineage_record)
        logger.info(f"Published lineage record to {{topic}}: {{msg_id}}")
    except Exception as e:
        logger.warning(f"Lineage publishing failed (non-fatal): {{e}}")


def _init_otel(dag_id):
    """Initialize OpenTelemetry if Dynatrace is configured. Call once at module level."""
    try:
        dt_url = Variable.get("dynatrace_otel_url", default_var="")
        dt_token = Variable.get("dynatrace_api_token", default_var="")
        if dt_url and dt_token:
            config = OTELConfig.for_dynatrace(
                service_name=dag_id,
                dynatrace_url=dt_url,
                dynatrace_token=dt_token,
                environment=Variable.get("environment", default_var="int"),
            )
            configure_otel(config)
            logger.info(f"OTEL initialized for {{dag_id}} → Dynatrace")
        else:
            # Try GCP Cloud Trace as fallback
            project_id = _get_project_id()
            if project_id:
                config = OTELConfig.for_gcp(
                    service_name=dag_id,
                    project_id=project_id,
                    environment=Variable.get("environment", default_var="int"),
                )
                configure_otel(config)
                logger.info(f"OTEL initialized for {{dag_id}} → GCP Cloud Trace")
    except Exception as e:
        logger.debug(f"OTEL init skipped (non-fatal): {{e}}")


def _create_otel_context(run_id, system_id, entity_type=None):
    """Create an OTELContext for tracing a pipeline run. Returns no-op if OTEL not initialized."""
    try:
        if is_otel_initialized():
            return OTELContext(run_id=run_id, system_id=system_id, entity_type=entity_type)
    except Exception:
        pass
    return None


def _push_cloud_monitoring_metric(metric_name, value, labels=None):
    """Push a custom metric to Cloud Monitoring. Graceful no-op on failure."""
    try:
        from google.cloud import monitoring_v3
        import time as _time

        project_id = _get_project_id()
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{{project_id}}"

        series = monitoring_v3.TimeSeries()
        series.metric.type = f"custom.googleapis.com/pipeline/{{metric_name}}"
        for k, v in (labels or {{}}).items():
            series.metric.labels[k] = str(v)
        series.resource.type = "global"
        series.resource.labels["project_id"] = project_id

        now = _time.time()
        interval = monitoring_v3.TimeInterval(
            {{"end_time": {{"seconds": int(now), "nanos": int((now % 1) * 1e9)}}}}
        )
        point = monitoring_v3.Point({{"interval": interval, "value": {{"double_value": float(value)}}}})
        series.points = [point]

        client.create_time_series(name=project_name, time_series=[series])
        logger.info(f"Cloud Monitoring: {{metric_name}}={{value}}")
    except Exception as e:
        logger.debug(f"Cloud Monitoring push failed (non-fatal): {{e}}")


def _log_observability_status(dag_id):
    """
    Log which observability backends are active at DAG load time.
    Never raises — purely informational.
    """
    try:
        status = []

        # Dynatrace alerts
        try:
            dt_url = Variable.get("dynatrace_environment_url")
            dt_token = Variable.get("dynatrace_api_token")
            if dt_url and dt_token:
                status.append(f"  Dynatrace alerts:     ACTIVE ({{dt_url}})")
            else:
                status.append("  Dynatrace alerts:     NOT CONFIGURED (empty dynatrace_environment_url or dynatrace_api_token)")
        except Exception:
            status.append("  Dynatrace alerts:     NOT CONFIGURED (missing Airflow Variables)")

        # ServiceNow incidents
        try:
            snow_url = Variable.get("servicenow_instance_url")
            snow_user = Variable.get("servicenow_username")
            if snow_url and snow_user:
                group = ""
                try:
                    group = Variable.get("servicenow_assignment_group", default_var="")
                except Exception:
                    pass
                detail = f"({{snow_url}}, group={{group}})" if group else f"({{snow_url}})"
                status.append(f"  ServiceNow incidents: ACTIVE {{detail}}")
            else:
                status.append("  ServiceNow incidents: NOT CONFIGURED (empty servicenow_instance_url or servicenow_username)")
        except Exception:
            status.append("  ServiceNow incidents: NOT CONFIGURED (missing Airflow Variables)")

        # Audit publishing
        try:
            topic = Variable.get("audit_pubsub_topic", default_var="generic-pipeline-events")
            status.append(f"  Audit publishing:     ACTIVE (topic: {{topic}})")
        except Exception:
            status.append("  Audit publishing:     ACTIVE (topic: generic-pipeline-events, default)")

        # FinOps cost tracking (always on — queries INFORMATION_SCHEMA)
        status.append("  FinOps cost tracking: ACTIVE (via INFORMATION_SCHEMA.JOBS)")

        # OTEL tracing
        try:
            dt_otel = Variable.get("dynatrace_otel_url", default_var="")
            if dt_otel:
                status.append(f"  OTEL tracing:         ACTIVE -> Dynatrace ({{dt_otel}})")
            else:
                project_id = Variable.get("gcp_project_id", default_var="")
                if project_id:
                    status.append(f"  OTEL tracing:         ACTIVE -> GCP Cloud Trace ({{project_id}})")
                else:
                    status.append("  OTEL tracing:         DISABLED (no dynatrace_otel_url or gcp_project_id)")
        except Exception:
            status.append("  OTEL tracing:         DISABLED (missing Airflow Variables)")

        # Cloud Monitoring
        try:
            project_id = Variable.get("gcp_project_id", default_var="")
            if project_id:
                status.append(f"  Cloud Monitoring:     ACTIVE (project: {{project_id}})")
            else:
                status.append("  Cloud Monitoring:     DISABLED (missing gcp_project_id)")
        except Exception:
            status.append("  Cloud Monitoring:     DISABLED (missing Airflow Variables)")

        logger.info(f"[OBSERVABILITY] {{dag_id}} startup:\n" + "\n".join(status))
    except Exception as e:
        logger.debug(f"Observability status check failed (non-fatal): {{e}}")

# =============================================================================
# Task callables
# =============================================================================

def scan_failed_jobs(**context) -> str:
    """
    Scan job_control for FAILED jobs from today.

    Routes to:
      - handle_critical: CRITICAL-stage failures (FILE_DISCOVERY, FDP_DEPENDENCY)
      - handle_retryable: ODP_LOAD, RECONCILIATION, FDP_MODEL failures under max retries
      - handle_manual_review: failures that exceeded max retries
      - no_errors: nothing to process
    """
    project_id = _get_project_id()
    today = datetime.now(tz=timezone.utc).date()
    repo = JobControlRepository(project_id=project_id)
    failed = repo.get_failed_jobs(SYSTEM_ID, today)

    if not failed:
        logger.info(f"No failed jobs for {SYSTEM_ID} on {today}")
        return "no_errors"

    critical = []
    retryable = []
    manual_review = []

    for job in failed:
        run_id = job["run_id"]
        entity = job["entity_type"]
        retry_count = job.get("retry_count", 0)

        # Get full job to check failure_stage
        full_job = repo.get_job(run_id)
        stage = full_job.failure_stage.value if full_job and full_job.failure_stage else "UNKNOWN"

        if stage in CRITICAL_STAGES:
            critical.append(job)
        elif stage in RETRYABLE_STAGES:
            # Check if ODP or FDP
            is_fdp = entity in FDP_MODELS
            max_retries = FDP_MAX_RETRIES if is_fdp else ODP_MAX_RETRIES
            if retry_count < max_retries:
                retryable.append({**job, "stage": stage, "is_fdp": is_fdp})
            else:
                manual_review.append({**job, "stage": stage, "exhausted_retries": True})
        else:
            manual_review.append({**job, "stage": stage})

    context["ti"].xcom_push(key="critical_jobs", value=critical)
    context["ti"].xcom_push(key="retryable_jobs", value=retryable)
    context["ti"].xcom_push(key="manual_review_jobs", value=manual_review)

    logger.info(f"Failed jobs: {len(critical)} critical, {len(retryable)} retryable, {len(manual_review)} manual review")

    if critical:
        return "handle_critical"
    elif retryable:
        return "handle_retryable"
    elif manual_review:
        return "handle_manual_review"
    else:
        return "no_errors"


def handle_critical(**context):
    """Alert immediately on critical failures — do NOT auto-retry."""
    critical_jobs = context["ti"].xcom_pull(key="critical_jobs") or []
    for job in critical_jobs:
        run_id = job["run_id"]
        entity = job["entity_type"]
        logger.error(f"CRITICAL failure: {run_id} entity={entity}")
        _send_failure_alert(
            dag_id=DAG_ID, task_id="handle_critical",
            exception=Exception(f"Critical pipeline failure for {entity}: {run_id}"),
            metadata={
                "run_id": run_id, "entity": entity,
                "severity": "CRITICAL", "action": "REQUIRES_MANUAL_INTERVENTION",
            },
        )
        # Publish failure audit
        _publish_audit(run_id, DAG_ID, entity, "error_handling", success=False, error_count=1,
                       metadata={"severity": "CRITICAL", "action": "alerted"})
    _push_cloud_monitoring_metric("error_handling_critical", len(critical_jobs), {"system": SYSTEM_ID})


def handle_retryable(**context):
    """Auto-retry eligible failed jobs. Cleanup partial ODP loads first."""
    from airflow.api.common.trigger_dag import trigger_dag

    project_id = _get_project_id()
    retryable_jobs = context["ti"].xcom_pull(key="retryable_jobs") or []
    repo = JobControlRepository(project_id=project_id)

    retried = 0
    for job in retryable_jobs:
        run_id = job["run_id"]
        entity = job["entity_type"]
        retry_count = job.get("retry_count", 0)
        is_fdp = job.get("is_fdp", False)

        # Cleanup partial ODP data before retry (if configured)
        if not is_fdp and ODP_CLEANUP_ON_RETRY:
            odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
            odp_table = f"{project_id}.{odp_dataset}.{entity}"
            try:
                deleted = repo.cleanup_partial_load(run_id, odp_table)
                logger.info(f"Cleaned up {deleted} partial rows from {odp_table} for {run_id}")
            except Exception as e:
                logger.warning(f"Cleanup failed for {run_id} (non-fatal): {e}")

        # Mark as retrying
        repo.mark_retrying(run_id, retry_count=retry_count + 1)

        # Trigger the appropriate DAG
        if is_fdp:
            target_dag = TRANSFORMATION_DAG_ID
            conf = {"fdp_model": entity, "extract_date": datetime.now(tz=timezone.utc).strftime("%Y%m%d"), "triggered_by": DAG_ID}
        else:
            target_dag = INGESTION_DAG_ID
            # Reconstruct file metadata for re-ingestion
            full_job = repo.get_job(run_id)
            source_file = full_job.source_files[0] if full_job and full_job.source_files else ""
            conf = {
                "file_metadata": json.dumps({
                    "entity": entity,
                    "data_file": source_file,
                    "extract_date": datetime.now(tz=timezone.utc).strftime("%Y%m%d"),
                }),
                "triggered_by": DAG_ID,
            }

        try:
            retry_run_id = f"retry_{run_id}_{retry_count + 1}"
            trigger_dag(dag_id=target_dag, run_id=retry_run_id, conf=conf, replace_microseconds=False)
            logger.info(f"Triggered retry for {run_id} → {target_dag} (attempt {retry_count + 1})")
            retried += 1
        except Exception as e:
            logger.error(f"Failed to trigger retry for {run_id}: {e}")
            _send_failure_alert(DAG_ID, "handle_retryable", e, {"run_id": run_id, "entity": entity})

    logger.info(f"Retried {retried}/{len(retryable_jobs)} failed jobs")
    _push_cloud_monitoring_metric("error_handling_retried", retried, {"system": SYSTEM_ID})


def handle_manual_review(**context):
    """Alert on jobs that need manual review (exhausted retries or config errors)."""
    manual_jobs = context["ti"].xcom_pull(key="manual_review_jobs") or []
    for job in manual_jobs:
        run_id = job["run_id"]
        entity = job["entity_type"]
        stage = job.get("stage", "UNKNOWN")
        exhausted = job.get("exhausted_retries", False)
        reason = "max retries exhausted" if exhausted else f"failure at {stage}"
        logger.warning(f"Manual review needed: {run_id} entity={entity} reason={reason}")
        _send_failure_alert(
            dag_id=DAG_ID, task_id="handle_manual_review",
            exception=Exception(f"Manual review needed for {entity}: {reason}"),
            metadata={
                "run_id": run_id, "entity": entity, "stage": stage,
                "severity": "WARNING", "action": "REQUIRES_MANUAL_REVIEW",
                "exhausted_retries": exhausted,
            },
        )
    _push_cloud_monitoring_metric("error_handling_manual_review", len(manual_jobs), {"system": SYSTEM_ID})


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=1),
}

generic_error_handling_dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Monitor and recover failed {SYSTEM_NAME} pipeline jobs — runs every 30 min",
    schedule="*/30 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=[FILE_PREFIX, "error", "recovery", "monitoring"],
)

with generic_error_handling_dag:
    scan = BranchPythonOperator(task_id="scan_failed_jobs", python_callable=scan_failed_jobs)
    critical = PythonOperator(task_id="handle_critical", python_callable=handle_critical)
    retryable = PythonOperator(task_id="handle_retryable", python_callable=handle_retryable)
    manual = PythonOperator(task_id="handle_manual_review", python_callable=handle_manual_review)
    no_errors = DummyOperator(task_id="no_errors")
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    scan >> [critical, retryable, manual, no_errors]
    [critical, retryable, manual, no_errors] >> end

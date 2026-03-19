# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dags.py
"""
Generic Pipeline Status DAG

Daily observer — queries job_control at end of day and alerts if
any entity or FDP model is missing or failed. Does not trigger anything.
Generated from system.yaml — all config baked in at build time.
"""

from datetime import datetime, timedelta
import logging
import os

from airflow import DAG
from airflow.models import Variable

try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator

from gcp_pipeline_core.job_control import JobControlRepository
from gcp_pipeline_core.monitoring.observability import ObservabilityManager
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
DAG_ID = "generic_pipeline_status_dag"


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
            title=f"Pipeline Failure: {dag_id}",
            message=f"Task `{task_id}` failed: {error_msg}",
            source=dag_id,
            metadata=metadata or {"task_id": task_id, "dag_id": dag_id},
        )
    except Exception as e:
        logger.warning(f"Slack alert failed (non-fatal): {e}")


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
            metadata=metadata or {},
        )
        publisher = AuditPublisher(project_id=project_id, topic_name=topic)
        msg_id = publisher.publish(record)
        logger.info(f"Published audit record to {topic}: {msg_id}")
    except Exception as e:
        logger.warning(f"Audit publishing failed (non-fatal): {e}")


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
            logger.info(f"FinOps: {run_id} cost=${cost_usd:.6f}, "
                         f"scanned={bytes_scanned:,} bytes, "
                         f"written={bytes_written:,} bytes, "
                         f"jobs={results[0].job_count}")
        else:
            logger.info(f"FinOps: no BQ jobs found with label run_id={run_id}")
    except Exception as e:
        logger.warning(f"FinOps cost tracking failed (non-fatal): {e}")


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
            metadata=metadata or {},
        )
        lineage = DataLineageTracker.generate_data_lineage(record)
        logger.info(f"Data lineage: {lineage}")
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
            metadata={"lineage": lineage, **(metadata or {})},
        )
        msg_id = publisher.publish(lineage_record)
        logger.info(f"Published lineage record to {topic}: {msg_id}")
    except Exception as e:
        logger.warning(f"Lineage publishing failed (non-fatal): {e}")


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
            logger.info(f"OTEL initialized for {dag_id} → Dynatrace")
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
                logger.info(f"OTEL initialized for {dag_id} → GCP Cloud Trace")
    except Exception as e:
        logger.debug(f"OTEL init skipped (non-fatal): {e}")


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
        project_name = f"projects/{project_id}"

        series = monitoring_v3.TimeSeries()
        series.metric.type = f"custom.googleapis.com/pipeline/{metric_name}"
        for k, v in (labels or {}).items():
            series.metric.labels[k] = str(v)
        series.resource.type = "global"
        series.resource.labels["project_id"] = project_id

        now = _time.time()
        interval = monitoring_v3.TimeInterval(
            {"end_time": {"seconds": int(now), "nanos": int((now % 1) * 1e9)}}
        )
        point = monitoring_v3.Point({"interval": interval, "value": {"double_value": float(value)}})
        series.points = [point]

        client.create_time_series(name=project_name, time_series=[series])
        logger.info(f"Cloud Monitoring: {metric_name}={value}")
    except Exception as e:
        logger.debug(f"Cloud Monitoring push failed (non-fatal): {e}")


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
                status.append(f"  Dynatrace alerts:     ACTIVE ({dt_url})")
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
                detail = f"({snow_url}, group={group})" if group else f"({snow_url})"
                status.append(f"  ServiceNow incidents: ACTIVE {detail}")
            else:
                status.append("  ServiceNow incidents: NOT CONFIGURED (empty servicenow_instance_url or servicenow_username)")
        except Exception:
            status.append("  ServiceNow incidents: NOT CONFIGURED (missing Airflow Variables)")

        # Audit publishing
        try:
            topic = Variable.get("audit_pubsub_topic", default_var="generic-pipeline-events")
            status.append(f"  Audit publishing:     ACTIVE (topic: {topic})")
        except Exception:
            status.append("  Audit publishing:     ACTIVE (topic: generic-pipeline-events, default)")

        # FinOps cost tracking (always on — queries INFORMATION_SCHEMA)
        status.append("  FinOps cost tracking: ACTIVE (via INFORMATION_SCHEMA.JOBS)")

        # OTEL tracing
        try:
            dt_otel = Variable.get("dynatrace_otel_url", default_var="")
            if dt_otel:
                status.append(f"  OTEL tracing:         ACTIVE -> Dynatrace ({dt_otel})")
            else:
                project_id = Variable.get("gcp_project_id", default_var="")
                if project_id:
                    status.append(f"  OTEL tracing:         ACTIVE -> GCP Cloud Trace ({project_id})")
                else:
                    status.append("  OTEL tracing:         DISABLED (no dynatrace_otel_url or gcp_project_id)")
        except Exception:
            status.append("  OTEL tracing:         DISABLED (missing Airflow Variables)")

        # Cloud Monitoring
        try:
            project_id = Variable.get("gcp_project_id", default_var="")
            if project_id:
                status.append(f"  Cloud Monitoring:     ACTIVE (project: {project_id})")
            else:
                status.append("  Cloud Monitoring:     DISABLED (missing gcp_project_id)")
        except Exception:
            status.append("  Cloud Monitoring:     DISABLED (missing Airflow Variables)")

        logger.info(f"[OBSERVABILITY] {dag_id} startup:\n" + "\n".join(status))
    except Exception as e:
        logger.debug(f"Observability status check failed (non-fatal): {e}")
# =============================================================================
# Task callable
# =============================================================================

def check_pipeline_status(**context):
    project_id = _get_project_id()
    today = context["ds_nodash"]
    date_obj = datetime.strptime(today, "%Y%m%d").date()
    repo = JobControlRepository(project_id=project_id)
    statuses = repo.get_entity_status(SYSTEM_ID, date_obj)
    status_map = {s["entity_type"]: s["status"] for s in statuses}

    # Use ObservabilityManager for health tracking
    obs = ObservabilityManager(
        pipeline_name=DAG_ID,
        run_id=f"status_{today}",
        alert_backends=_get_alert_manager().backends,
    )

    total_checks = len(ENTITIES) + len(FDP_MODELS)
    succeeded = 0
    failed = 0
    issues = []

    for entity in ENTITIES:
        status = status_map.get(entity)
        if status == "SUCCESS":
            logger.info(f"  ODP {entity}: SUCCESS")
            succeeded += 1
            obs.report_records_processed(1, {"layer": "ODP", "entity": entity})
        elif status == "FAILED":
            issues.append(f"ODP {entity}: FAILED")
            failed += 1
            obs.report_records_error(1, {"layer": "ODP", "entity": entity})
            logger.error(f"  ODP {entity}: FAILED")
        else:
            issues.append(f"ODP {entity}: NOT LOADED (status={status})")
            failed += 1
            obs.report_records_error(1, {"layer": "ODP", "entity": entity})
            logger.warning(f"  ODP {entity}: NOT LOADED")

    for model in FDP_MODELS:
        status = status_map.get(model)
        if status == "SUCCESS":
            logger.info(f"  FDP {model}: SUCCESS")
            succeeded += 1
            obs.report_records_processed(1, {"layer": "FDP", "model": model})
        elif status == "FAILED":
            issues.append(f"FDP {model}: FAILED")
            failed += 1
            obs.report_records_error(1, {"layer": "FDP", "model": model})
            logger.error(f"  FDP {model}: FAILED")
        else:
            issues.append(f"FDP {model}: NOT RUN (status={status})")
            failed += 1
            obs.report_records_error(1, {"layer": "FDP", "model": model})
            logger.warning(f"  FDP {model}: NOT RUN")

    # Health check — error rate threshold
    error_rate = failed / total_checks if total_checks > 0 else 0
    health_ok = obs.check_health()
    summary_data = obs.get_summary()

    logger.info(f"Health: succeeded={succeeded}/{total_checks}, "
                f"error_rate={error_rate:.0%}, healthy={health_ok}")
    logger.info(f"Observability summary: {summary_data}")

    if issues:
        summary = f"{SYSTEM_NAME} pipeline incomplete for {today}:\n" + "\n".join(f"  - {i}" for i in issues)
        # Alert via Dynatrace + ServiceNow
        _send_failure_alert(
            dag_id=DAG_ID, task_id="check_pipeline_status",
            exception=Exception(summary),
            metadata={
                "date": today,
                "issues_count": len(issues),
                "error_rate": f"{error_rate:.0%}",
                "succeeded": succeeded,
                "total": total_checks,
                "issues": [i[:100] for i in issues],
            },
        )
        raise Exception(summary)
    logger.info(f"{SYSTEM_NAME} pipeline complete for {today} — {len(ENTITIES)} entities, {len(FDP_MODELS)} FDP models all succeeded.")


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
    "retry_delay": timedelta(minutes=5),
}

generic_pipeline_status_dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Daily status check for {SYSTEM_NAME} pipeline completeness — alerts on gaps or failures",
    schedule="0 23 * * *",
    catchup=False,
    tags=[FILE_PREFIX, "status", "observability"],
)

with generic_pipeline_status_dag:
    PythonOperator(task_id="check_pipeline_status", python_callable=check_pipeline_status)

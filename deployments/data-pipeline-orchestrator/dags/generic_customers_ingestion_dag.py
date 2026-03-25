# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dags.py
"""
Generic Customers Ingestion DAG

Runs Dataflow to load customers data to BigQuery ODP, reconciles,
checks FDP dependencies, and triggers ready transformations.
Generated from system.yaml — all config baked in at build time.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import json
import logging
import os

from airflow import DAG
from airflow.models import Variable

try:
    from airflow.providers.standard.operators.python import PythonOperator
    from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
except ImportError:
    from airflow.operators.python import PythonOperator
    try:
        from airflow.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator

from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator
from gcp_pipeline_core.audit import AuditTrail, ReconciliationEngine
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob, FailureStage
from gcp_pipeline_core.error_handling import ErrorHandler, GCSErrorStorage
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
ENTITY = "customers"
ENTITIES = ['customers', 'accounts', 'decision', 'applications']
FDP_DEPENDENCIES = {'event_transaction_excess': ['customers', 'accounts'], 'portfolio_account_excess': ['decision'], 'portfolio_account_facility': ['applications']}
DAG_ID = "generic_customers_ingestion_dag"
TRANSFORMATION_DAG_MAP = {'event_transaction_excess': 'generic_event_transaction_excess_transformation_dag', 'portfolio_account_excess': 'generic_portfolio_account_excess_transformation_dag', 'portfolio_account_facility': 'generic_portfolio_account_facility_transformation_dag'}

# Infrastructure templates
ODP_DATASET_TEMPLATE = "odp_{system}"
ERROR_BUCKET_TEMPLATE = "{project_id}-{system}-{env}-error"
TEMP_BUCKET_TEMPLATE = "{project_id}-{system}-{env}-temp"


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
    """Send alert on task failure via Dynatrace/ServiceNow. Graceful no-op if not configured."""
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
        logger.warning(f"Alert dispatch failed (non-fatal): {e}")


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
        record.metadata = {"lineage": lineage, **(metadata or {})}
        msg_id = publisher.publish(record)
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
# Task callables
# =============================================================================

def mark_job_failed(context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="run_id")
    task_id = context["task_instance"].task_id
    exception = context.get("exception")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        stage_map = {
            "create_job_record": FailureStage.FILE_DISCOVERY,
            "run_dataflow_pipeline": FailureStage.ODP_LOAD,
            "update_job_success": FailureStage.ODP_LOAD,
            "reconcile_odp_load": FailureStage.RECONCILIATION,
            "check_ready_fdp_models": FailureStage.ODP_LOAD,
            "trigger_ready_transforms": FailureStage.ODP_LOAD,
        }
        stage = stage_map.get(task_id, FailureStage.ODP_LOAD)
        error_code = type(exception).__name__ if exception else "UNKNOWN"
        error_message = str(exception)[:1024] if exception else f"Task {task_id} failed"
        repo.mark_failed(run_id=run_id, error_code=error_code, error_message=error_message, failure_stage=stage)
        if exception:
            try:
                error_bucket = _resolve(ERROR_BUCKET_TEMPLATE)
                error_storage = GCSErrorStorage(bucket_name=error_bucket, prefix=f"error_logs/{run_id}")
                handler = ErrorHandler(pipeline_name=DAG_ID, run_id=run_id, error_storage=error_storage)
                handler.handle_exception(exception, source_file=task_id)
            except Exception as e:
                logger.warning(f"Error handler storage failed (non-fatal): {e}")
        entity = context["ti"].xcom_pull(key="entity") or "unknown"
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=entity)
        audit.record_processing_start(source_file="unknown")
        audit.log_entry("FAILURE", f"Task {task_id} failed: {error_message}")
        audit.record_processing_end(success=False)
        # Alert on failure
        _send_failure_alert(DAG_ID, task_id, exception, {"run_id": run_id, "entity": entity, "stage": stage.value})
        # Publish failure audit record
        _publish_audit(run_id, DAG_ID, entity, "unknown", success=False, error_count=1,
                       metadata={"error_code": error_code, "failure_stage": stage.value})
        _push_cloud_monitoring_metric("odp_load_failure", 1, {"entity": entity, "system": SYSTEM_ID, "stage": stage.value})
        logger.error(f"Job {run_id} marked FAILED at stage {stage.value}: {error_code}")


def create_job_record(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {}
    file_metadata_raw = conf.get("file_metadata", {})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    entity = ENTITY
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    data_file = file_metadata.get("data_file", "")
    run_id = context.get("run_id", f"{FILE_PREFIX}_{entity}_{extract_date}")
    extract_date_obj = datetime.strptime(extract_date, "%Y%m%d").date() if extract_date else datetime.now(tz=timezone.utc).date()

    repo = JobControlRepository(project_id=project_id)
    existing = repo.get_entity_status(SYSTEM_ID, extract_date_obj)
    for entry in existing:
        if entry["entity_type"] == entity and entry["status"] == "FAILED":
            old_run_id = entry["run_id"]
            odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
            odp_table = f"{project_id}.{odp_dataset}.{entity}"
            logger.info(f"Found failed job {old_run_id}. Cleaning up partial data from {odp_table}")
            try:
                deleted = repo.cleanup_partial_load(old_run_id, odp_table)
                logger.info(f"Cleaned up {deleted} partial rows from {odp_table} for run {old_run_id}")
            except Exception as e:
                logger.warning(f"Cleanup of partial load failed (non-fatal): {e}")
            repo.mark_retrying(old_run_id, retry_count=1)

    job = PipelineJob(
        run_id=run_id, system_id=SYSTEM_ID, entity_type=entity,
        extract_date=extract_date_obj, source_files=[data_file],
        started_at=datetime.now(tz=timezone.utc), job_type="ODP_INGESTION",
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)
    logger.info(f"Created job record: {run_id} for entity: {entity}")
    context["ti"].xcom_push(key="run_id", value=run_id)
    context["ti"].xcom_push(key="entity", value=entity)


def check_ready_fdp_models(**context) -> None:
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {}
    file_metadata_raw = conf.get("file_metadata", {})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    checker = EntityDependencyChecker(project_id=project_id, system_id=SYSTEM_ID, required_entities=ENTITIES)
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    loaded = set(checker.get_loaded_entities(date_obj))
    ready_models = [model for model, deps in FDP_DEPENDENCIES.items() if set(deps).issubset(loaded)]
    if ready_models:
        logger.info(f"FDP models ready to run: {ready_models} (loaded entities: {loaded})")
    else:
        logger.info(f"No FDP models ready yet. Loaded entities: {loaded}")
    context["ti"].xcom_push(key="ready_fdp_models", value=ready_models)


def update_job_success(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="run_id")
    entity = context["ti"].xcom_pull(key="entity")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"Job {run_id} marked as SUCCESS")
        conf = context.get("dag_run").conf or {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
        data_file = file_metadata.get("data_file", "unknown")
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=entity or "unknown")
        audit.record_processing_start(source_file=data_file, metadata={"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID})
        audit.record_processing_end(success=True)
        # Publish success audit record to Pub/Sub
        _publish_audit(run_id, DAG_ID, entity or "unknown", data_file, success=True,
                       metadata={"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID})
        # Data lineage tracking
        _publish_lineage(run_id, DAG_ID, entity or "unknown", data_file, success=True,
                         metadata={"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID})
        # Track FinOps cost from BigQuery jobs labelled with this run_id
        _track_pipeline_cost(run_id)
        # Push to Cloud Monitoring
        _push_cloud_monitoring_metric("odp_load_success", 1, {"entity": entity or "unknown", "system": SYSTEM_ID})


def reconcile_odp_load(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="run_id")
    entity = context["ti"].xcom_pull(key="entity")
    conf = context.get("dag_run").conf or {}
    hdr_metadata_raw = conf.get("hdr_metadata", {})
    hdr_metadata = json.loads(hdr_metadata_raw) if isinstance(hdr_metadata_raw, str) else hdr_metadata_raw
    expected_count = hdr_metadata.get("record_count") if hdr_metadata else None
    if not expected_count:
        logger.warning(f"No expected record count from HDR/TRL for {entity}. Skipping reconciliation.")
        return
    odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    odp_table = f"{project_id}.{odp_dataset}.{entity}"
    error_table = f"{project_id}.{odp_dataset}.{entity}_errors"
    engine = ReconciliationEngine(entity_type=entity, run_id=run_id, project_id=project_id)
    result = engine.reconcile_with_bigquery(
        expected_count=expected_count, destination_table=odp_table, error_table=error_table,
    )
    if not result.is_reconciled:
        raise Exception(
            f"ODP reconciliation MISMATCH for {entity}: "
            f"expected={result.expected_count}, actual={result.actual_count}, "
            f"errors={result.error_count}, match={result.match_percentage:.1f}%"
        )
    logger.info(f"ODP reconciliation passed for {entity}: {result.actual_count}/{result.expected_count} rows")


def trigger_ready_transforms(**context):
    from airflow.api.common.trigger_dag import trigger_dag
    ready_models = context["ti"].xcom_pull(key="ready_fdp_models", task_ids="check_ready_fdp_models") or []
    conf = context.get("dag_run").conf or {}
    file_metadata_raw = conf.get("file_metadata", {})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    if not ready_models:
        logger.info("No FDP models ready. Skipping transformation trigger.")
        return
    for model in ready_models:
        target_dag = TRANSFORMATION_DAG_MAP.get(model)
        if not target_dag:
            logger.warning(f"No transformation DAG for model '{model}' — skipping")
            continue
        run_id = f"transform_{model}_{extract_date}"
        logger.info(f"Triggering {target_dag} for model: {model}")
        trigger_dag(
            dag_id=target_dag, run_id=run_id,
            conf={"extract_date": extract_date, "fdp_model": model, "triggered_by": DAG_ID},
            replace_microseconds=False,
        )


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2026, 1, 1),
    "on_failure_callback": mark_job_failed,
}

_project_id = _get_project_id()
_odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
_template_bucket = Variable.get("dataflow_templates_bucket", default_var=_resolve(TEMP_BUCKET_TEMPLATE))

generic_customers_ingestion_dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Load {SYSTEM_NAME} {ENTITY} data to ODP (BigQuery)",
    schedule=None,
    catchup=False,
    tags=[FILE_PREFIX, "odp", "dataflow", ENTITY],
)

with generic_customers_ingestion_dag:
    create_job = PythonOperator(task_id="create_job_record", python_callable=create_job_record)
    run_dataflow = BaseDataflowOperator(
        task_id="run_dataflow_pipeline",
        pipeline_name=f"{FILE_PREFIX}-odp-load",
        project_id=_project_id,
        region=Variable.get("gcp_region", default_var="europe-west2"),
        source_type="gcs",
        processing_mode="batch",
        template_type="flex",
        input_path="{{ dag_run.conf.data_file }}",
        output_table=f"{_project_id}:{_odp_dataset}.{ENTITY}",
        template_path=f"gs://{_template_bucket}/templates/{FILE_PREFIX}_pipeline.json",
        use_template=True,
        additional_params={
            "run_id": '{{ ti.xcom_pull(key="run_id") }}',
            "source_file": "{{ dag_run.conf.data_file }}",
            "entity": ENTITY,
            "extract_date": "{{ dag_run.conf.extract_date }}",
        },
    )
    mark_success = PythonOperator(task_id="update_job_success", python_callable=update_job_success)
    reconcile = PythonOperator(task_id="reconcile_odp_load", python_callable=reconcile_odp_load)
    check_deps = PythonOperator(task_id="check_ready_fdp_models", python_callable=check_ready_fdp_models)
    trigger_transforms = PythonOperator(task_id="trigger_ready_transforms", python_callable=trigger_ready_transforms)
    end = DummyOperator(task_id="end")

    create_job >> run_dataflow >> mark_success >> reconcile >> check_deps >> trigger_transforms >> end

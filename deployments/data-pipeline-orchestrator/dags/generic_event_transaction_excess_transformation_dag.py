# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dags.py
"""
Generic event_transaction_excess Transformation DAG

Transforms ODP to FDP for event_transaction_excess — runs per-model based on granular dependencies.
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
    from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
    from airflow.providers.standard.operators.bash import BashOperator
    from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
except ImportError:
    from airflow.operators.python import PythonOperator, BranchPythonOperator
    from airflow.operators.bash import BashOperator
    try:
        from airflow.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator

from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
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
FDP_MODEL = "event_transaction_excess"
REQUIRED_ENTITIES = ['customers', 'accounts']
ENTITIES = ['customers', 'accounts', 'decision', 'applications']
FDP_DEPENDENCIES = {'event_transaction_excess': ['customers', 'accounts'], 'portfolio_account_excess': ['decision'], 'portfolio_account_facility': ['applications']}
DAG_ID = "generic_event_transaction_excess_transformation_dag"

# Infrastructure templates
ODP_DATASET_TEMPLATE = "odp_{system}"
FDP_DATASET_TEMPLATE = "fdp_{system}"
ERROR_BUCKET_TEMPLATE = "{project_id}-{system}-{env}-error"


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

def mark_fdp_job_failed(context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="fdp_run_id")
    task_id = context["task_instance"].task_id
    exception = context.get("exception")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        stage_map = {
            "verify_model_dependencies": FailureStage.FDP_DEPENDENCY,
            "create_fdp_job_record": FailureStage.FDP_DEPENDENCY,
            "run_dbt_staging": FailureStage.FDP_STAGING,
            "run_dbt_fdp": FailureStage.FDP_MODEL,
            "run_dbt_tests": FailureStage.FDP_TEST,
            "reconcile_fdp_model": FailureStage.RECONCILIATION,
        }
        stage = stage_map.get(task_id, FailureStage.TRANSFORMATION)
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
        conf = context.get("dag_run").conf or {}
        fdp_model = FDP_MODEL
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=fdp_model)
        audit.record_processing_start(source_file=f"odp_{FILE_PREFIX}.*")
        audit.log_entry("FAILURE", f"Task {task_id} failed: {error_message}")
        audit.record_processing_end(success=False)
        # Alert on FDP failure
        _send_failure_alert(DAG_ID, task_id, exception, {"run_id": run_id, "fdp_model": fdp_model, "stage": stage.value})
        # Publish failure audit record
        _publish_audit(run_id, DAG_ID, fdp_model, f"odp_{FILE_PREFIX}.*", success=False, error_count=1,
                       metadata={"error_code": error_code, "failure_stage": stage.value})
        _push_cloud_monitoring_metric("fdp_transform_failure", 1, {"model": fdp_model, "system": SYSTEM_ID, "stage": stage.value})
        logger.error(f"FDP job {run_id} marked FAILED at stage {stage.value}: {error_code}")


def verify_model_dependencies(**context) -> str:
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {}
    fdp_model = FDP_MODEL
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    if not fdp_model or fdp_model not in FDP_DEPENDENCIES:
        logger.error(f"Unknown or missing FDP model: '{fdp_model}'. Expected one of: {list(FDP_DEPENDENCIES.keys())}")
        return "handle_dependency_failure"
    required_entities = FDP_DEPENDENCIES[fdp_model]
    checker = EntityDependencyChecker(project_id=project_id, system_id=SYSTEM_ID, required_entities=required_entities)
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    if checker.all_entities_loaded(date_obj):
        logger.info(f"Dependencies satisfied for {fdp_model}: {required_entities}. Proceeding.")
        context["ti"].xcom_push(key="fdp_model", value=fdp_model)
        context["ti"].xcom_push(key="required_entities", value=required_entities)
        return "create_fdp_job_record"
    else:
        missing = checker.get_missing_entities(date_obj)
        logger.warning(f"Cannot run {fdp_model}. Missing entities: {missing}")
        context["ti"].xcom_push(key="missing_entities", value=missing)
        return "handle_dependency_failure"


def create_fdp_job_record(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {}
    fdp_model = FDP_MODEL
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    run_id = context.get("run_id", f"transform_{fdp_model}_{extract_date}")
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    repo = JobControlRepository(project_id=project_id)
    required_entities = FDP_DEPENDENCIES.get(fdp_model, [])
    parent_statuses = repo.get_entity_status(SYSTEM_ID, date_obj)
    parent_run_ids = [
        s["run_id"] for s in parent_statuses
        if s["entity_type"] in required_entities and s["status"] == "SUCCESS"
    ]
    job = PipelineJob(
        run_id=run_id, system_id=SYSTEM_ID, entity_type=fdp_model,
        extract_date=date_obj, started_at=datetime.now(tz=timezone.utc),
        job_type="FDP_TRANSFORMATION", dbt_model_name=fdp_model, parent_run_ids=parent_run_ids,
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)
    logger.info(f"Created FDP job record: {run_id} for model: {fdp_model}, parents: {parent_run_ids}")
    context["ti"].xcom_push(key="fdp_run_id", value=run_id)


def handle_dependency_failure(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {}
    fdp_model = FDP_MODEL
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    run_id = context.get("run_id", f"transform_{fdp_model}_{extract_date}")
    missing = context["ti"].xcom_pull(key="missing_entities") or []
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    repo = JobControlRepository(project_id=project_id)
    job = PipelineJob(
        run_id=run_id, system_id=SYSTEM_ID, entity_type=fdp_model,
        extract_date=date_obj, started_at=datetime.now(tz=timezone.utc),
        job_type="FDP_TRANSFORMATION", dbt_model_name=fdp_model,
    )
    repo.create_job(job)
    repo.mark_failed(
        run_id=run_id, error_code="DEPENDENCY_NOT_MET",
        error_message=f"Missing ODP entities: {missing}. DAG triggered prematurely.",
        failure_stage=FailureStage.FDP_DEPENDENCY,
    )
    logger.error(f"FDP dependency failure recorded for {fdp_model}: missing {missing}")
    context["ti"].xcom_push(key="fdp_run_id", value=run_id)


def update_fdp_job_success(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="fdp_run_id")
    conf = context.get("dag_run").conf or {}
    fdp_model = FDP_MODEL
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"FDP job {run_id} marked as SUCCESS")
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=fdp_model)
        audit.record_processing_start(
            source_file=f"odp_{FILE_PREFIX}.*",
            metadata={"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model},
        )
        audit.record_processing_end(success=True)
        # Publish success audit record to Pub/Sub
        _publish_audit(run_id, DAG_ID, fdp_model, f"odp_{FILE_PREFIX}.*", success=True,
                       metadata={"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model})
        # Data lineage tracking
        _publish_lineage(run_id, DAG_ID, fdp_model, f"odp_{FILE_PREFIX}.*", success=True,
                         metadata={"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model})
        # Track FinOps cost from dbt's BigQuery jobs
        _track_pipeline_cost(run_id)
        # Push to Cloud Monitoring
        _push_cloud_monitoring_metric("fdp_transform_success", 1, {"model": fdp_model, "system": SYSTEM_ID})


def reconcile_fdp_model_output(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="fdp_run_id")
    conf = context.get("dag_run").conf or {}
    fdp_model = FDP_MODEL
    fdp_dataset = FDP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    fdp_table = f"{project_id}.{fdp_dataset}.{fdp_model}"
    required_entities = FDP_DEPENDENCIES.get(fdp_model, [])
    odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    source_tables = [f"{project_id}.{odp_dataset}.{e}" for e in required_entities]
    model_info = dict(FDP_DEPENDENCIES)  # type info not available here, default to inner
    join_type = "inner"
    engine = ReconciliationEngine(entity_type=fdp_model, run_id=run_id, project_id=project_id)
    result = engine.reconcile_fdp_model(
        model_name=fdp_model, source_tables=source_tables,
        destination_table=fdp_table, join_type=join_type,
    )
    if not result.is_reconciled:
        raise Exception(f"FDP reconciliation MISMATCH for {fdp_model}: {result.message}")
    logger.info(f"FDP reconciliation passed for {fdp_model}: {result.actual_count} rows")


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)

_dbt_project_path = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "start_date": datetime(2026, 1, 1),
    "on_failure_callback": mark_fdp_job_failed,
}

generic_event_transaction_excess_transformation_dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Transform {SYSTEM_NAME} ODP to FDP — {FDP_MODEL}",
    schedule=None,
    catchup=False,
    tags=[FILE_PREFIX, "fdp", "dbt", "transformation", FDP_MODEL],
)

with generic_event_transaction_excess_transformation_dag:
    verify = BranchPythonOperator(task_id="verify_model_dependencies", python_callable=verify_model_dependencies)
    create_fdp_job = PythonOperator(task_id="create_fdp_job_record", python_callable=create_fdp_job_record)
    staging = BashOperator(
        task_id="run_dbt_staging",
        bash_command=f"cd {_dbt_project_path} && dbt run --select staging --vars '{{\"extract_date\": \"{{{{ ds_nodash }}}}\"}}' --target prod",
    )
    fdp = BashOperator(
        task_id="run_dbt_fdp",
        bash_command=f"cd {_dbt_project_path} && dbt run --select '{FDP_MODEL}' --vars '{{\"extract_date\": \"{{{{ ds_nodash }}}}\"}}' --target prod",
    )
    tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command=f"cd {_dbt_project_path} && dbt test --select '{FDP_MODEL}' --target prod",
    )
    reconcile_fdp = PythonOperator(task_id="reconcile_fdp_model", python_callable=reconcile_fdp_model_output)
    mark_success = PythonOperator(task_id="mark_fdp_success", python_callable=update_fdp_job_success)
    dep_failure = PythonOperator(task_id="handle_dependency_failure", python_callable=handle_dependency_failure)
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    verify >> [create_fdp_job, dep_failure]
    create_fdp_job >> staging >> fdp >> tests >> reconcile_fdp >> mark_success >> end
    dep_failure >> end

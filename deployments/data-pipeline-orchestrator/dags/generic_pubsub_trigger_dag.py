# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dags.py
"""
Generic Pub/Sub Trigger DAG

Listens for .ok files via Pub/Sub and triggers ODP load.
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
    from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
    from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
except ImportError:
    from airflow.operators.python import PythonOperator, BranchPythonOperator
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator
    try:
        from airflow.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator

from gcp_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor
from gcp_pipeline_core.file_management import HDRTRLParser
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
OK_FILE_SUFFIX = ".ok"
ENTITIES = ['customers', 'accounts', 'decision', 'applications']
DAG_ID = "generic_pubsub_trigger_dag"
INGESTION_DAG_ID = "generic_ingestion_dag"
TRIGGER_SCHEDULE = "*/1 * * * *"

# Infrastructure templates (resolved at runtime with project_id/env)
PUBSUB_SUBSCRIPTION_TEMPLATE = "{system}-file-notifications-sub"
ERROR_BUCKET_TEMPLATE = "{project_id}-{system}-{env}-error"


# =============================================================================
# Runtime resolution (only project_id and env come from Airflow Variables)
# =============================================================================

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
# Task callables
# =============================================================================

def parse_pubsub_message(**context) -> Dict[str, Any]:
    messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")
    if not messages:
        logger.warning("No messages received from Pub/Sub")
        return {"status": "no_message"}
    message = messages[0] if isinstance(messages, list) else messages

    file_name = ""
    bucket = ""

    if isinstance(message, str):
        message_data = json.loads(message)
        file_name = message_data.get("name", "")
        bucket = message_data.get("bucket", "")
    elif isinstance(message, dict):
        file_name = message.get("name", "")
        bucket = message.get("bucket", "")
        if not file_name:
            nested_msg = message.get("message", {})
            attributes = nested_msg.get("attributes", {}) if isinstance(nested_msg, dict) else {}
            file_name = attributes.get("objectId", "")
            bucket = attributes.get("bucketId", "")
            if not file_name:
                data = nested_msg.get("data", "") if isinstance(nested_msg, dict) else ""
                if data:
                    try:
                        import base64
                        if isinstance(data, bytes):
                            data_str = data.decode("utf-8")
                        else:
                            try:
                                data_str = base64.b64decode(data).decode("utf-8")
                            except Exception:
                                data_str = data
                        data_json = json.loads(data_str)
                        file_name = data_json.get("name", "")
                        bucket = data_json.get("bucket", "")
                    except Exception as e:
                        logger.debug(f"Could not parse message data: {e}")
    else:
        file_name = getattr(message, "name", "") or ""
        bucket = getattr(message, "bucket", "") or ""

    logger.info(f"Received notification for: gs://{bucket}/{file_name}")

    if not file_name.endswith(OK_FILE_SUFFIX):
        logger.info(f"Skipping non-OK file: {file_name}")
        return {"status": "skip", "reason": "not_ok_file", "file_name": file_name}

    extract_date = None
    base_name = file_name.replace(OK_FILE_SUFFIX, "")
    for part in base_name.split("_"):
        if part.isdigit() and len(part) == 8:
            extract_date = part
            break

    trigger_file = f"gs://{bucket}/{file_name}"
    data_file = f"gs://{bucket}/{file_name.replace(OK_FILE_SUFFIX, '.csv')}"

    result = {
        "status": "success",
        "trigger_file": trigger_file,
        "data_file": data_file,
        "entity": entity,
        "extract_date": extract_date,
        "bucket": bucket,
        "file_name": file_name,
    }
    logger.info(f"Parsed file metadata: {result}")
    context["ti"].xcom_push(key="file_metadata", value=result)
    return result


def validate_file(**context) -> str:
    from google.cloud import storage
    file_metadata = context["ti"].xcom_pull(task_ids="parse_message")
    if not file_metadata or file_metadata.get("status") != "success":
        return "skip_processing"
    data_file = file_metadata.get("data_file", "")
    bucket_name = file_metadata.get("bucket", "")
    try:
        client = storage.Client()
        bucket_obj = client.bucket(bucket_name)
        blob_path = data_file.replace(f"gs://{bucket_name}/", "")
        blob = bucket_obj.blob(blob_path)
        if not blob.exists():
            logger.error(f"Data file not found: {data_file}")
            return "handle_validation_error"
        content = blob.download_as_text()
        lines = content.strip().split("\n")
        parser = HDRTRLParser()
        metadata = parser.parse_file_lines(lines)
        if metadata.header.system_id.upper() != SYSTEM_ID.upper():
            logger.error(f"System ID mismatch: expected {SYSTEM_ID}, got {metadata.header.system_id}")
            return "handle_validation_error"
        context["ti"].xcom_push(key="hdr_metadata", value={
            "system_id": metadata.header.system_id,
            "entity_type": metadata.header.entity_type,
            "extract_date": str(metadata.header.extract_date),
            "record_count": metadata.trailer.record_count,
        })
        logger.info(f"File validated: {metadata.header.system_id}/{metadata.header.entity_type}")
        run_id = context["run_id"]
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=file_metadata.get("entity", "unknown"))
        audit.record_processing_start(source_file=data_file)
        audit.log_entry(status="INFO", message=f"File validated: record_count={metadata.trailer.record_count}")
        return "trigger_odp_load"
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        return "handle_validation_error"


def move_to_error_bucket(**context):
    from google.cloud import storage
    file_metadata = context["ti"].xcom_pull(task_ids="parse_message")
    if not file_metadata or file_metadata.get("status") != "success":
        return
    # Alert on validation failure
    _send_failure_alert(
        dag_id=DAG_ID, task_id="handle_validation_error",
        exception=Exception(f"File validation failed for {file_metadata.get('file_name', 'unknown')}"),
        metadata={"entity": file_metadata.get("entity"), "file": file_metadata.get("file_name")},
    )
    error_bucket = _resolve(ERROR_BUCKET_TEMPLATE)
    client = storage.Client()
    source_bucket = client.bucket(file_metadata.get("bucket"))
    dest_bucket = client.bucket(error_bucket)
    for file_key in ["data_file", "ok_file"]:
        file_path = file_metadata.get(file_key, "")
        if file_path:
            blob_path = file_path.replace(f"gs://{file_metadata.get('bucket')}/", "")
            source_blob = source_bucket.blob(blob_path)
            if source_blob.exists():
                dest_path = f"validation_errors/{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}/{blob_path}"
                source_bucket.copy_blob(source_blob, dest_bucket, dest_path)
                source_blob.delete()
                logger.info(f"Moved {blob_path} to error bucket")


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
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

generic_pubsub_trigger_dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Listen for {SYSTEM_NAME} file arrivals via Pub/Sub and trigger ODP load",
    schedule=TRIGGER_SCHEDULE,
    catchup=False,
    max_active_runs=1,
    tags=[FILE_PREFIX, "trigger", "pubsub"],
)

with generic_pubsub_trigger_dag:
    pubsub_subscription = Variable.get(
        f"{FILE_PREFIX}_pubsub_subscription",
        default_var=_resolve(PUBSUB_SUBSCRIPTION_TEMPLATE),
    )
    wait_for_file = BasePubSubPullSensor(
        task_id="wait_for_file_notification",
        project_id=Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", "")),
        subscription=pubsub_subscription,
        max_messages=1,
        filter_extension=OK_FILE_SUFFIX,
        metadata_xcom_key="file_metadata",
        poke_interval=10,
        timeout=55,
        mode="reschedule",
        soft_fail=True,
    )
    parse_message = PythonOperator(task_id="parse_message", python_callable=parse_pubsub_message)
    validate = BranchPythonOperator(task_id="validate_file", python_callable=validate_file)
    trigger_odp = TriggerDagRunOperator(
        task_id="trigger_odp_load",
        trigger_dag_id=INGESTION_DAG_ID,
        conf={
            "file_metadata": "{{ ti.xcom_pull(task_ids='parse_message') | tojson }}",
            "hdr_metadata": "{{ ti.xcom_pull(task_ids='validate_file', key='hdr_metadata') | tojson }}",
            "data_file": "{{ ti.xcom_pull(task_ids='parse_message').data_file }}",
            "entity": "{{ ti.xcom_pull(task_ids='parse_message').entity }}",
            "extract_date": "{{ ti.xcom_pull(task_ids='parse_message').extract_date }}",
        },
        wait_for_completion=False,
    )
    handle_error = PythonOperator(task_id="handle_validation_error", python_callable=move_to_error_bucket)
    skip = DummyOperator(task_id="skip_processing")
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    wait_for_file >> parse_message >> validate
    validate >> [trigger_odp, handle_error, skip]
    [trigger_odp, handle_error, skip] >> end

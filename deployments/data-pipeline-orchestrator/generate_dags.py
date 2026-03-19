"""
DAG Generator — Config-Driven from system.yaml

Generates concrete, static Airflow DAG Python files from the system.yaml
configuration file. The generated DAGs have all config baked in as constants,
so Airflow's scheduler never needs to read YAML or run factory logic at parse time.

This is the same pattern used by generate_dbt_models.py for the dbt layer.

Usage:
    python generate_dags.py [--config CONFIG_PATH] [--output OUTPUT_DIR] [--dry-run]

Examples:
    # Generate DAGs (default: reads config/system.yaml, writes to dags/)
    python generate_dags.py

    # Dry run to preview what would be generated
    python generate_dags.py --dry-run

    # Custom config and output
    python generate_dags.py --config /path/to/system.yaml --output /path/to/dags/
"""

import argparse
import logging
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

GENERATED_HEADER = '# Auto-generated from system.yaml — DO NOT EDIT MANUALLY\n# To modify, update system.yaml and re-run: python generate_dags.py\n'


OBSERVABILITY_IMPORTS = """\
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
"""

# NOTE: This block uses single braces for Python code (dict literals, f-strings).
# It is injected via {observability_helpers} inside the f-string templates,
# so all Python braces must be DOUBLE-escaped ({{ }}) when inside an f-string.
OBSERVABILITY_HELPERS = '''

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

        logger.info(f"[OBSERVABILITY] {dag_id} startup:\\n" + "\\n".join(status))
    except Exception as e:
        logger.debug(f"Observability status check failed (non-fatal): {e}")
'''


def _build_dag_code(imports_section: str, config_section: str, task_section: str) -> str:
    """
    Build a complete DAG file by concatenating sections.

    The OBSERVABILITY_IMPORTS and OBSERVABILITY_HELPERS blocks contain raw Python
    code with braces (dicts, f-strings) that must NOT be escaped. They are
    concatenated as-is between the config and task sections.

    Args:
        imports_section: Airflow/library imports (no config substitution needed)
        config_section: Baked-in constants (already has config values substituted)
        task_section: Task callables + DAG definition (already has config values substituted)

    Returns:
        Complete DAG file as a string
    """
    return (
        GENERATED_HEADER
        + imports_section
        + OBSERVABILITY_IMPORTS
        + config_section
        + OBSERVABILITY_HELPERS
        + task_section
    )


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load and validate system.yaml."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    if "system_id" not in config:
        raise ValueError("Config missing 'system_id'")
    if "entities" not in config:
        raise ValueError("Config missing 'entities' section")
    return config


def _should_write(filepath: Path) -> bool:
    """Only overwrite files that have the auto-generated header or don't exist."""
    if not filepath.exists():
        return True
    content = filepath.read_text()
    return "Auto-generated from system.yaml" in content


def _entity_names(config: Dict[str, Any]) -> List[str]:
    return list(config.get("entities", {}).keys())


def _fdp_dependencies(config: Dict[str, Any]) -> Dict[str, List[str]]:
    return {
        model: info["requires"]
        for model, info in config.get("fdp_models", {}).items()
    }


# =============================================================================
# DAG 1: Pub/Sub Trigger DAG
# =============================================================================

def generate_pubsub_trigger_dag(config: Dict[str, Any]) -> str:
    """Generate the Pub/Sub trigger DAG as a concrete Python file."""
    system_id = config["system_id"]
    system_id_lower = system_id.lower()
    system_name = config.get("system_name", system_id)
    file_prefix = config.get("file_prefix", system_id_lower)
    ok_file_suffix = config.get("ok_file_suffix", ".ok")
    entities = _entity_names(config)
    trigger_schedule = config.get("trigger_schedule", "*/1 * * * *")

    infra = config.get("infrastructure", {})
    pubsub = infra.get("pubsub", {})
    buckets = infra.get("buckets", {})
    error_bucket_template = buckets.get("error", "")

    pubsub_subscription_template = pubsub.get("subscription", "")

    ingestion_dag_id = f"{system_id_lower}_ingestion_dag"
    dag_id = f"{system_id_lower}_pubsub_trigger_dag"

    imports_section = textwrap.dedent('''\
"""
''' + f'{system_name}' + ''' Pub/Sub Trigger DAG

Listens for ''' + f'{ok_file_suffix}' + ''' files via Pub/Sub and triggers ODP load.
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
''')

    config_section = textwrap.dedent(f'''\
logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "{system_id}"
SYSTEM_NAME = "{system_name}"
FILE_PREFIX = "{file_prefix}"
OK_FILE_SUFFIX = "{ok_file_suffix}"
ENTITIES = {entities!r}
DAG_ID = "{dag_id}"
INGESTION_DAG_ID = "{ingestion_dag_id}"
TRIGGER_SCHEDULE = "{trigger_schedule}"

# Infrastructure templates (resolved at runtime with project_id/env)
PUBSUB_SUBSCRIPTION_TEMPLATE = "{pubsub_subscription_template}"
ERROR_BUCKET_TEMPLATE = "{error_bucket_template}"


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

''')

    task_section = textwrap.dedent(f'''\
# =============================================================================
# Task callables
# =============================================================================

def parse_pubsub_message(**context) -> Dict[str, Any]:
    messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")
    if not messages:
        logger.warning("No messages received from Pub/Sub")
        return {{"status": "no_message"}}
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
            nested_msg = message.get("message", {{}})
            attributes = nested_msg.get("attributes", {{}}) if isinstance(nested_msg, dict) else {{}}
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
                        logger.debug(f"Could not parse message data: {{e}}")
    else:
        file_name = getattr(message, "name", "") or ""
        bucket = getattr(message, "bucket", "") or ""

    logger.info(f"Received notification for: gs://{{bucket}}/{{file_name}}")

    if not file_name.endswith(OK_FILE_SUFFIX):
        logger.info(f"Skipping non-OK file: {{file_name}}")
        return {{"status": "skip", "reason": "not_ok_file", "file_name": file_name}}

    extract_date = None
    base_name = file_name.replace(OK_FILE_SUFFIX, "")
    for part in base_name.split("_"):
        if part.isdigit() and len(part) == 8:
            extract_date = part
            break

    trigger_file = f"gs://{{bucket}}/{{file_name}}"
    data_file = f"gs://{{bucket}}/{{file_name.replace(OK_FILE_SUFFIX, '.csv')}}"

    result = {{
        "status": "success",
        "trigger_file": trigger_file,
        "data_file": data_file,
        "entity": entity,
        "extract_date": extract_date,
        "bucket": bucket,
        "file_name": file_name,
    }}
    logger.info(f"Parsed file metadata: {{result}}")
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
        blob_path = data_file.replace(f"gs://{{bucket_name}}/", "")
        blob = bucket_obj.blob(blob_path)
        if not blob.exists():
            logger.error(f"Data file not found: {{data_file}}")
            return "handle_validation_error"
        content = blob.download_as_text()
        lines = content.strip().split("\\n")
        parser = HDRTRLParser()
        metadata = parser.parse_file_lines(lines)
        if metadata.header.system_id.upper() != SYSTEM_ID.upper():
            logger.error(f"System ID mismatch: expected {{SYSTEM_ID}}, got {{metadata.header.system_id}}")
            return "handle_validation_error"
        context["ti"].xcom_push(key="hdr_metadata", value={{
            "system_id": metadata.header.system_id,
            "entity_type": metadata.header.entity_type,
            "extract_date": str(metadata.header.extract_date),
            "record_count": metadata.trailer.record_count,
        }})
        logger.info(f"File validated: {{metadata.header.system_id}}/{{metadata.header.entity_type}}")
        run_id = context["run_id"]
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=file_metadata.get("entity", "unknown"))
        audit.record_processing_start(source_file=data_file)
        audit.log_entry(status="INFO", message=f"File validated: record_count={{metadata.trailer.record_count}}")
        return "trigger_odp_load"
    except Exception as e:
        logger.error(f"File validation failed: {{e}}")
        return "handle_validation_error"


def move_to_error_bucket(**context):
    from google.cloud import storage
    file_metadata = context["ti"].xcom_pull(task_ids="parse_message")
    if not file_metadata or file_metadata.get("status") != "success":
        return
    # Alert on validation failure
    _send_failure_alert(
        dag_id=DAG_ID, task_id="handle_validation_error",
        exception=Exception(f"File validation failed for {{file_metadata.get('file_name', 'unknown')}}"),
        metadata={{"entity": file_metadata.get("entity"), "file": file_metadata.get("file_name")}},
    )
    error_bucket = _resolve(ERROR_BUCKET_TEMPLATE)
    client = storage.Client()
    source_bucket = client.bucket(file_metadata.get("bucket"))
    dest_bucket = client.bucket(error_bucket)
    for file_key in ["data_file", "ok_file"]:
        file_path = file_metadata.get(file_key, "")
        if file_path:
            blob_path = file_path.replace(f"gs://{{file_metadata.get('bucket')}}/", "")
            source_blob = source_bucket.blob(blob_path)
            if source_blob.exists():
                dest_path = f"validation_errors/{{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}}/{{blob_path}}"
                source_bucket.copy_blob(source_blob, dest_bucket, dest_path)
                source_blob.delete()
                logger.info(f"Moved {{blob_path}} to error bucket")


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}}

{dag_id} = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Listen for {{SYSTEM_NAME}} file arrivals via Pub/Sub and trigger ODP load",
    schedule=TRIGGER_SCHEDULE,
    catchup=False,
    max_active_runs=1,
    tags=[FILE_PREFIX, "trigger", "pubsub"],
)

with {dag_id}:
    pubsub_subscription = Variable.get(
        f"{{FILE_PREFIX}}_pubsub_subscription",
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
        conf={{
            "file_metadata": "{{{{ ti.xcom_pull(task_ids='parse_message') | tojson }}}}",
            "hdr_metadata": "{{{{ ti.xcom_pull(task_ids='validate_file', key='hdr_metadata') | tojson }}}}",
            "data_file": "{{{{ ti.xcom_pull(task_ids='parse_message').data_file }}}}",
            "entity": "{{{{ ti.xcom_pull(task_ids='parse_message').entity }}}}",
            "extract_date": "{{{{ ti.xcom_pull(task_ids='parse_message').extract_date }}}}",
        }},
        wait_for_completion=False,
    )
    handle_error = PythonOperator(task_id="handle_validation_error", python_callable=move_to_error_bucket)
    skip = DummyOperator(task_id="skip_processing")
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    wait_for_file >> parse_message >> validate
    validate >> [trigger_odp, handle_error, skip]
    [trigger_odp, handle_error, skip] >> end
''')

    return _build_dag_code(imports_section, config_section, task_section)


# =============================================================================
# DAG 2: Ingestion DAG
# =============================================================================

def generate_ingestion_dag(config: Dict[str, Any]) -> str:
    """Generate the ingestion DAG as a concrete Python file."""
    system_id = config["system_id"]
    system_id_lower = system_id.lower()
    system_name = config.get("system_name", system_id)
    file_prefix = config.get("file_prefix", system_id_lower)
    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)

    infra = config.get("infrastructure", {})
    datasets = infra.get("datasets", {})
    odp_dataset_template = datasets.get("odp", "odp_{system}")
    buckets = infra.get("buckets", {})
    error_bucket_template = buckets.get("error", "")
    temp_bucket_template = buckets.get("temp", "")

    dag_id = f"{system_id_lower}_ingestion_dag"
    transformation_dag_id = f"{system_id_lower}_transformation_dag"

    imports_section = textwrap.dedent('''\
"""
''' + f'{system_name}' + ''' Ingestion DAG

Runs Dataflow to load entity data to BigQuery ODP, reconciles,
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
''')

    config_section = textwrap.dedent(f'''\
logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "{system_id}"
SYSTEM_NAME = "{system_name}"
FILE_PREFIX = "{file_prefix}"
ENTITIES = {entities!r}
FDP_DEPENDENCIES = {fdp_deps!r}
DAG_ID = "{dag_id}"
TRANSFORMATION_DAG_ID = "{transformation_dag_id}"

# Infrastructure templates
ODP_DATASET_TEMPLATE = "{odp_dataset_template}"
ERROR_BUCKET_TEMPLATE = "{error_bucket_template}"
TEMP_BUCKET_TEMPLATE = "{temp_bucket_template}"


def _resolve(template: str) -> str:
    project_id = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
    env = Variable.get("environment", default_var="int")
    return template.format(
        project_id=project_id, system=FILE_PREFIX, env=env, file_prefix=FILE_PREFIX,
    )


def _get_project_id() -> str:
    return Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))

''')

    task_section = textwrap.dedent(f'''\
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
        stage_map = {{
            "create_job_record": FailureStage.FILE_DISCOVERY,
            "run_dataflow_pipeline": FailureStage.ODP_LOAD,
            "update_job_success": FailureStage.ODP_LOAD,
            "reconcile_odp_load": FailureStage.RECONCILIATION,
            "check_ready_fdp_models": FailureStage.ODP_LOAD,
            "trigger_ready_transforms": FailureStage.ODP_LOAD,
        }}
        stage = stage_map.get(task_id, FailureStage.ODP_LOAD)
        error_code = type(exception).__name__ if exception else "UNKNOWN"
        error_message = str(exception)[:1024] if exception else f"Task {{task_id}} failed"
        repo.mark_failed(run_id=run_id, error_code=error_code, error_message=error_message, failure_stage=stage)
        if exception:
            try:
                error_bucket = _resolve(ERROR_BUCKET_TEMPLATE)
                error_storage = GCSErrorStorage(bucket_name=error_bucket, prefix=f"error_logs/{{run_id}}")
                handler = ErrorHandler(pipeline_name=DAG_ID, run_id=run_id, error_storage=error_storage)
                handler.handle_exception(exception, source_file=task_id)
            except Exception as e:
                logger.warning(f"Error handler storage failed (non-fatal): {{e}}")
        entity = context["ti"].xcom_pull(key="entity") or "unknown"
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=entity)
        audit.record_processing_start(source_file="unknown")
        audit.log_entry("FAILURE", f"Task {{task_id}} failed: {{error_message}}")
        audit.record_processing_end(success=False)
        # Slack alert on failure
        _send_failure_alert(DAG_ID, task_id, exception, {{"run_id": run_id, "entity": entity, "stage": stage.value}})
        # Publish failure audit record
        _publish_audit(run_id, DAG_ID, entity, "unknown", success=False, error_count=1,
                       metadata={{"error_code": error_code, "failure_stage": stage.value}})
        _push_cloud_monitoring_metric("odp_load_failure", 1, {{"entity": entity, "system": SYSTEM_ID, "stage": stage.value}})
        logger.error(f"Job {{run_id}} marked FAILED at stage {{stage.value}}: {{error_code}}")


def create_job_record(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {{}}
    file_metadata_raw = conf.get("file_metadata", {{}})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    entity = file_metadata.get("entity", "unknown")
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    data_file = file_metadata.get("data_file", "")
    run_id = context.get("run_id", f"{{FILE_PREFIX}}_{{entity}}_{{extract_date}}")
    extract_date_obj = datetime.strptime(extract_date, "%Y%m%d").date() if extract_date else datetime.now(tz=timezone.utc).date()

    repo = JobControlRepository(project_id=project_id)
    existing = repo.get_entity_status(SYSTEM_ID, extract_date_obj)
    for entry in existing:
        if entry["entity_type"] == entity and entry["status"] == "FAILED":
            old_run_id = entry["run_id"]
            odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
            odp_table = f"{{project_id}}.{{odp_dataset}}.{{entity}}"
            logger.info(f"Found failed job {{old_run_id}}. Cleaning up partial data from {{odp_table}}")
            try:
                deleted = repo.cleanup_partial_load(old_run_id, odp_table)
                logger.info(f"Cleaned up {{deleted}} partial rows from {{odp_table}} for run {{old_run_id}}")
            except Exception as e:
                logger.warning(f"Cleanup of partial load failed (non-fatal): {{e}}")
            repo.mark_retrying(old_run_id, retry_count=1)

    job = PipelineJob(
        run_id=run_id, system_id=SYSTEM_ID, entity_type=entity,
        extract_date=extract_date_obj, source_files=[data_file],
        started_at=datetime.now(tz=timezone.utc), job_type="ODP_INGESTION",
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)
    logger.info(f"Created job record: {{run_id}} for entity: {{entity}}")
    context["ti"].xcom_push(key="run_id", value=run_id)
    context["ti"].xcom_push(key="entity", value=entity)


def check_ready_fdp_models(**context) -> None:
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {{}}
    file_metadata_raw = conf.get("file_metadata", {{}})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    checker = EntityDependencyChecker(project_id=project_id, system_id=SYSTEM_ID, required_entities=ENTITIES)
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    loaded = set(checker.get_loaded_entities(date_obj))
    ready_models = [model for model, deps in FDP_DEPENDENCIES.items() if set(deps).issubset(loaded)]
    if ready_models:
        logger.info(f"FDP models ready to run: {{ready_models}} (loaded entities: {{loaded}})")
    else:
        logger.info(f"No FDP models ready yet. Loaded entities: {{loaded}}")
    context["ti"].xcom_push(key="ready_fdp_models", value=ready_models)


def update_job_success(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="run_id")
    entity = context["ti"].xcom_pull(key="entity")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"Job {{run_id}} marked as SUCCESS")
        conf = context.get("dag_run").conf or {{}}
        file_metadata_raw = conf.get("file_metadata", {{}})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
        data_file = file_metadata.get("data_file", "unknown")
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=entity or "unknown")
        audit.record_processing_start(source_file=data_file, metadata={{"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID}})
        audit.record_processing_end(success=True)
        # Publish success audit record to Pub/Sub
        _publish_audit(run_id, DAG_ID, entity or "unknown", data_file, success=True,
                       metadata={{"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID}})
        # Data lineage tracking
        _publish_lineage(run_id, DAG_ID, entity or "unknown", data_file, success=True,
                         metadata={{"job_type": "ODP_INGESTION", "system_id": SYSTEM_ID}})
        # Track FinOps cost from BigQuery jobs labelled with this run_id
        _track_pipeline_cost(run_id)
        # Push to Cloud Monitoring
        _push_cloud_monitoring_metric("odp_load_success", 1, {{"entity": entity or "unknown", "system": SYSTEM_ID}})


def reconcile_odp_load(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="run_id")
    entity = context["ti"].xcom_pull(key="entity")
    conf = context.get("dag_run").conf or {{}}
    hdr_metadata_raw = conf.get("hdr_metadata", {{}})
    hdr_metadata = json.loads(hdr_metadata_raw) if isinstance(hdr_metadata_raw, str) else hdr_metadata_raw
    expected_count = hdr_metadata.get("record_count") if hdr_metadata else None
    if not expected_count:
        logger.warning(f"No expected record count from HDR/TRL for {{entity}}. Skipping reconciliation.")
        return
    odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    odp_table = f"{{project_id}}.{{odp_dataset}}.{{entity}}"
    error_table = f"{{project_id}}.{{odp_dataset}}.{{entity}}_errors"
    engine = ReconciliationEngine(entity_type=entity, run_id=run_id, project_id=project_id)
    result = engine.reconcile_with_bigquery(
        expected_count=expected_count, destination_table=odp_table, error_table=error_table,
    )
    if not result.is_reconciled:
        raise Exception(
            f"ODP reconciliation MISMATCH for {{entity}}: "
            f"expected={{result.expected_count}}, actual={{result.actual_count}}, "
            f"errors={{result.error_count}}, match={{result.match_percentage:.1f}}%"
        )
    logger.info(f"ODP reconciliation passed for {{entity}}: {{result.actual_count}}/{{result.expected_count}} rows")


def trigger_ready_transforms(**context):
    from airflow.api.common.trigger_dag import trigger_dag
    ready_models = context["ti"].xcom_pull(key="ready_fdp_models", task_ids="check_ready_fdp_models") or []
    conf = context.get("dag_run").conf or {{}}
    file_metadata_raw = conf.get("file_metadata", {{}})
    file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
    extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    if not ready_models:
        logger.info("No FDP models ready. Skipping transformation trigger.")
        return
    for model in ready_models:
        run_id = f"transform_{{model}}_{{extract_date}}"
        logger.info(f"Triggering {{TRANSFORMATION_DAG_ID}} for model: {{model}}")
        trigger_dag(
            dag_id=TRANSFORMATION_DAG_ID, run_id=run_id,
            conf={{"extract_date": extract_date, "fdp_model": model, "triggered_by": DAG_ID}},
            replace_microseconds=False,
        )


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2026, 1, 1),
    "on_failure_callback": mark_job_failed,
}}

_project_id = _get_project_id()
_odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
_template_bucket = Variable.get("dataflow_templates_bucket", default_var=_resolve(TEMP_BUCKET_TEMPLATE))

{dag_id} = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Load {{SYSTEM_NAME}} entity data to ODP (BigQuery)",
    schedule=None,
    catchup=False,
    tags=[FILE_PREFIX, "odp", "dataflow"],
)

with {dag_id}:
    create_job = PythonOperator(task_id="create_job_record", python_callable=create_job_record)
    run_dataflow = BaseDataflowOperator(
        task_id="run_dataflow_pipeline",
        pipeline_name=f"{{FILE_PREFIX}}-odp-load",
        project_id=_project_id,
        region=Variable.get("gcp_region", default_var="europe-west2"),
        source_type="gcs",
        processing_mode="batch",
        input_path="{{{{ dag_run.conf.data_file }}}}",
        output_table=f"{{_project_id}}:{{_odp_dataset}}." + "{{{{ dag_run.conf.entity }}}}",
        template_path=f"gs://{{_template_bucket}}/templates/{{FILE_PREFIX}}_pipeline.json",
        use_template=True,
        additional_params={{"run_id": '{{{{ ti.xcom_pull(key="run_id") }}}}'}},
    )
    mark_success = PythonOperator(task_id="update_job_success", python_callable=update_job_success)
    reconcile = PythonOperator(task_id="reconcile_odp_load", python_callable=reconcile_odp_load)
    check_deps = PythonOperator(task_id="check_ready_fdp_models", python_callable=check_ready_fdp_models)
    trigger_transforms = PythonOperator(task_id="trigger_ready_transforms", python_callable=trigger_ready_transforms)
    end = DummyOperator(task_id="end")

    create_job >> run_dataflow >> mark_success >> reconcile >> check_deps >> trigger_transforms >> end
''')

    return _build_dag_code(imports_section, config_section, task_section)


# =============================================================================
# DAG 3: Transformation DAG
# =============================================================================

def generate_transformation_dag(config: Dict[str, Any]) -> str:
    """Generate the transformation DAG as a concrete Python file."""
    system_id = config["system_id"]
    system_id_lower = system_id.lower()
    system_name = config.get("system_name", system_id)
    file_prefix = config.get("file_prefix", system_id_lower)
    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)

    infra = config.get("infrastructure", {})
    datasets = infra.get("datasets", {})
    odp_dataset_template = datasets.get("odp", "odp_{system}")
    fdp_dataset_template = datasets.get("fdp", "fdp_{system}")
    buckets = infra.get("buckets", {})
    error_bucket_template = buckets.get("error", "")

    dag_id = f"{system_id_lower}_transformation_dag"

    imports_section = textwrap.dedent('''\
"""
''' + f'{system_name}' + ''' Transformation DAG

Transforms ODP to FDP — runs per-model based on granular dependencies.
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
''')

    config_section = textwrap.dedent(f'''\
logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "{system_id}"
SYSTEM_NAME = "{system_name}"
FILE_PREFIX = "{file_prefix}"
ENTITIES = {entities!r}
FDP_DEPENDENCIES = {fdp_deps!r}
DAG_ID = "{dag_id}"

# Infrastructure templates
ODP_DATASET_TEMPLATE = "{odp_dataset_template}"
FDP_DATASET_TEMPLATE = "{fdp_dataset_template}"
ERROR_BUCKET_TEMPLATE = "{error_bucket_template}"


def _resolve(template: str) -> str:
    project_id = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
    env = Variable.get("environment", default_var="int")
    return template.format(
        project_id=project_id, system=FILE_PREFIX, env=env, file_prefix=FILE_PREFIX,
    )


def _get_project_id() -> str:
    return Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))

''')

    task_section = textwrap.dedent(f'''\
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
        stage_map = {{
            "verify_model_dependencies": FailureStage.FDP_DEPENDENCY,
            "create_fdp_job_record": FailureStage.FDP_DEPENDENCY,
            "run_dbt_staging": FailureStage.FDP_STAGING,
            "run_dbt_fdp": FailureStage.FDP_MODEL,
            "run_dbt_tests": FailureStage.FDP_TEST,
            "reconcile_fdp_model": FailureStage.RECONCILIATION,
        }}
        stage = stage_map.get(task_id, FailureStage.TRANSFORMATION)
        error_code = type(exception).__name__ if exception else "UNKNOWN"
        error_message = str(exception)[:1024] if exception else f"Task {{task_id}} failed"
        repo.mark_failed(run_id=run_id, error_code=error_code, error_message=error_message, failure_stage=stage)
        if exception:
            try:
                error_bucket = _resolve(ERROR_BUCKET_TEMPLATE)
                error_storage = GCSErrorStorage(bucket_name=error_bucket, prefix=f"error_logs/{{run_id}}")
                handler = ErrorHandler(pipeline_name=DAG_ID, run_id=run_id, error_storage=error_storage)
                handler.handle_exception(exception, source_file=task_id)
            except Exception as e:
                logger.warning(f"Error handler storage failed (non-fatal): {{e}}")
        conf = context.get("dag_run").conf or {{}}
        fdp_model = conf.get("fdp_model", "unknown")
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=fdp_model)
        audit.record_processing_start(source_file=f"odp_{{FILE_PREFIX}}.*")
        audit.log_entry("FAILURE", f"Task {{task_id}} failed: {{error_message}}")
        audit.record_processing_end(success=False)
        # Slack alert on FDP failure
        _send_failure_alert(DAG_ID, task_id, exception, {{"run_id": run_id, "fdp_model": fdp_model, "stage": stage.value}})
        # Publish failure audit record
        _publish_audit(run_id, DAG_ID, fdp_model, f"odp_{{FILE_PREFIX}}.*", success=False, error_count=1,
                       metadata={{"error_code": error_code, "failure_stage": stage.value}})
        _push_cloud_monitoring_metric("fdp_transform_failure", 1, {{"model": fdp_model, "system": SYSTEM_ID, "stage": stage.value}})
        logger.error(f"FDP job {{run_id}} marked FAILED at stage {{stage.value}}: {{error_code}}")


def verify_model_dependencies(**context) -> str:
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {{}}
    fdp_model = conf.get("fdp_model", "")
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    if not fdp_model or fdp_model not in FDP_DEPENDENCIES:
        logger.error(f"Unknown or missing FDP model: '{{fdp_model}}'. Expected one of: {{list(FDP_DEPENDENCIES.keys())}}")
        return "handle_dependency_failure"
    required_entities = FDP_DEPENDENCIES[fdp_model]
    checker = EntityDependencyChecker(project_id=project_id, system_id=SYSTEM_ID, required_entities=required_entities)
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    if checker.all_entities_loaded(date_obj):
        logger.info(f"Dependencies satisfied for {{fdp_model}}: {{required_entities}}. Proceeding.")
        context["ti"].xcom_push(key="fdp_model", value=fdp_model)
        context["ti"].xcom_push(key="required_entities", value=required_entities)
        return "create_fdp_job_record"
    else:
        missing = checker.get_missing_entities(date_obj)
        logger.warning(f"Cannot run {{fdp_model}}. Missing entities: {{missing}}")
        context["ti"].xcom_push(key="missing_entities", value=missing)
        return "handle_dependency_failure"


def create_fdp_job_record(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {{}}
    fdp_model = conf.get("fdp_model", "")
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    run_id = context.get("run_id", f"transform_{{fdp_model}}_{{extract_date}}")
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
    logger.info(f"Created FDP job record: {{run_id}} for model: {{fdp_model}}, parents: {{parent_run_ids}}")
    context["ti"].xcom_push(key="fdp_run_id", value=run_id)


def handle_dependency_failure(**context):
    project_id = _get_project_id()
    conf = context.get("dag_run").conf or {{}}
    fdp_model = conf.get("fdp_model", "unknown")
    extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
    run_id = context.get("run_id", f"transform_{{fdp_model}}_{{extract_date}}")
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
        error_message=f"Missing ODP entities: {{missing}}. DAG triggered prematurely.",
        failure_stage=FailureStage.FDP_DEPENDENCY,
    )
    logger.error(f"FDP dependency failure recorded for {{fdp_model}}: missing {{missing}}")
    context["ti"].xcom_push(key="fdp_run_id", value=run_id)


def update_fdp_job_success(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="fdp_run_id")
    conf = context.get("dag_run").conf or {{}}
    fdp_model = conf.get("fdp_model", "unknown")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"FDP job {{run_id}} marked as SUCCESS")
        audit = AuditTrail(run_id=run_id, pipeline_name=DAG_ID, entity_type=fdp_model)
        audit.record_processing_start(
            source_file=f"odp_{{FILE_PREFIX}}.*",
            metadata={{"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model}},
        )
        audit.record_processing_end(success=True)
        # Publish success audit record to Pub/Sub
        _publish_audit(run_id, DAG_ID, fdp_model, f"odp_{{FILE_PREFIX}}.*", success=True,
                       metadata={{"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model}})
        # Data lineage tracking
        _publish_lineage(run_id, DAG_ID, fdp_model, f"odp_{{FILE_PREFIX}}.*", success=True,
                         metadata={{"job_type": "FDP_TRANSFORMATION", "system_id": SYSTEM_ID, "dbt_model": fdp_model}})
        # Track FinOps cost from dbt's BigQuery jobs
        _track_pipeline_cost(run_id)
        # Push to Cloud Monitoring
        _push_cloud_monitoring_metric("fdp_transform_success", 1, {{"model": fdp_model, "system": SYSTEM_ID}})


def reconcile_fdp_model_output(**context):
    project_id = _get_project_id()
    run_id = context["ti"].xcom_pull(key="fdp_run_id")
    conf = context.get("dag_run").conf or {{}}
    fdp_model = conf.get("fdp_model", "")
    fdp_dataset = FDP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    fdp_table = f"{{project_id}}.{{fdp_dataset}}.{{fdp_model}}"
    required_entities = FDP_DEPENDENCIES.get(fdp_model, [])
    odp_dataset = ODP_DATASET_TEMPLATE.format(system=FILE_PREFIX)
    source_tables = [f"{{project_id}}.{{odp_dataset}}.{{e}}" for e in required_entities]
    model_info = dict(FDP_DEPENDENCIES)  # type info not available here, default to inner
    join_type = "inner"
    engine = ReconciliationEngine(entity_type=fdp_model, run_id=run_id, project_id=project_id)
    result = engine.reconcile_fdp_model(
        model_name=fdp_model, source_tables=source_tables,
        destination_table=fdp_table, join_type=join_type,
    )
    if not result.is_reconciled:
        raise Exception(f"FDP reconciliation MISMATCH for {{fdp_model}}: {{result.message}}")
    logger.info(f"FDP reconciliation passed for {{fdp_model}}: {{result.actual_count}} rows")


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)

_dbt_project_path = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "start_date": datetime(2026, 1, 1),
    "on_failure_callback": mark_fdp_job_failed,
}}

{dag_id} = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Transform {{SYSTEM_NAME}} ODP to FDP — runs per-model based on granular dependencies",
    schedule=None,
    catchup=False,
    tags=[FILE_PREFIX, "fdp", "dbt", "transformation"],
)

with {dag_id}:
    verify = BranchPythonOperator(task_id="verify_model_dependencies", python_callable=verify_model_dependencies)
    create_fdp_job = PythonOperator(task_id="create_fdp_job_record", python_callable=create_fdp_job_record)
    staging = BashOperator(
        task_id="run_dbt_staging",
        bash_command=f"cd {{_dbt_project_path}} && dbt run --select staging --vars '{{{{\\\"extract_date\\\": \\\"{{{{{{{{ ds_nodash }}}}}}}}\\\"}}}}' --target prod",
    )
    fdp = BashOperator(
        task_id="run_dbt_fdp",
        bash_command=f"cd {{_dbt_project_path}} && dbt run --select '{{{{{{{{ dag_run.conf.fdp_model }}}}}}}}' --vars '{{{{\\\"extract_date\\\": \\\"{{{{{{{{ ds_nodash }}}}}}}}\\\"}}}}' --target prod",
    )
    tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command=f"cd {{_dbt_project_path}} && dbt test --select '{{{{{{{{ dag_run.conf.fdp_model }}}}}}}}' --target prod",
    )
    reconcile_fdp = PythonOperator(task_id="reconcile_fdp_model", python_callable=reconcile_fdp_model_output)
    mark_success = PythonOperator(task_id="mark_fdp_success", python_callable=update_fdp_job_success)
    dep_failure = PythonOperator(task_id="handle_dependency_failure", python_callable=handle_dependency_failure)
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    verify >> [create_fdp_job, dep_failure]
    create_fdp_job >> staging >> fdp >> tests >> reconcile_fdp >> mark_success >> end
    dep_failure >> end
''')

    return _build_dag_code(imports_section, config_section, task_section)


# =============================================================================
# DAG 4: Pipeline Status DAG
# =============================================================================

def generate_pipeline_status_dag(config: Dict[str, Any]) -> str:
    """Generate the pipeline status DAG as a concrete Python file."""
    system_id = config["system_id"]
    system_id_lower = system_id.lower()
    system_name = config.get("system_name", system_id)
    file_prefix = config.get("file_prefix", system_id_lower)
    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)

    dag_id = f"{system_id_lower}_pipeline_status_dag"

    imports_section = textwrap.dedent('''\
"""
''' + f'{system_name}' + ''' Pipeline Status DAG

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
''')

    config_section = textwrap.dedent(f'''\
logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "{system_id}"
SYSTEM_NAME = "{system_name}"
FILE_PREFIX = "{file_prefix}"
ENTITIES = {entities!r}
FDP_MODELS = {list(fdp_deps.keys())!r}
DAG_ID = "{dag_id}"


def _get_project_id() -> str:
    return Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))

''')

    task_section = textwrap.dedent(f'''\
# =============================================================================
# Task callable
# =============================================================================

def check_pipeline_status(**context):
    project_id = _get_project_id()
    today = context["ds_nodash"]
    date_obj = datetime.strptime(today, "%Y%m%d").date()
    repo = JobControlRepository(project_id=project_id)
    statuses = repo.get_entity_status(SYSTEM_ID, date_obj)
    status_map = {{s["entity_type"]: s["status"] for s in statuses}}

    # Use ObservabilityManager for health tracking
    obs = ObservabilityManager(
        pipeline_name=DAG_ID,
        run_id=f"status_{{today}}",
        alert_backends=_get_alert_manager().backends,
    )

    total_checks = len(ENTITIES) + len(FDP_MODELS)
    succeeded = 0
    failed = 0
    issues = []

    for entity in ENTITIES:
        status = status_map.get(entity)
        if status == "SUCCESS":
            logger.info(f"  ODP {{entity}}: SUCCESS")
            succeeded += 1
            obs.report_records_processed(1, {{"layer": "ODP", "entity": entity}})
        elif status == "FAILED":
            issues.append(f"ODP {{entity}}: FAILED")
            failed += 1
            obs.report_records_error(1, {{"layer": "ODP", "entity": entity}})
            logger.error(f"  ODP {{entity}}: FAILED")
        else:
            issues.append(f"ODP {{entity}}: NOT LOADED (status={{status}})")
            failed += 1
            obs.report_records_error(1, {{"layer": "ODP", "entity": entity}})
            logger.warning(f"  ODP {{entity}}: NOT LOADED")

    for model in FDP_MODELS:
        status = status_map.get(model)
        if status == "SUCCESS":
            logger.info(f"  FDP {{model}}: SUCCESS")
            succeeded += 1
            obs.report_records_processed(1, {{"layer": "FDP", "model": model}})
        elif status == "FAILED":
            issues.append(f"FDP {{model}}: FAILED")
            failed += 1
            obs.report_records_error(1, {{"layer": "FDP", "model": model}})
            logger.error(f"  FDP {{model}}: FAILED")
        else:
            issues.append(f"FDP {{model}}: NOT RUN (status={{status}})")
            failed += 1
            obs.report_records_error(1, {{"layer": "FDP", "model": model}})
            logger.warning(f"  FDP {{model}}: NOT RUN")

    # Health check — error rate threshold
    error_rate = failed / total_checks if total_checks > 0 else 0
    health_ok = obs.check_health()
    summary_data = obs.get_summary()

    logger.info(f"Health: succeeded={{succeeded}}/{{total_checks}}, "
                f"error_rate={{error_rate:.0%}}, healthy={{health_ok}}")
    logger.info(f"Observability summary: {{summary_data}}")

    if issues:
        summary = f"{{SYSTEM_NAME}} pipeline incomplete for {{today}}:\\n" + "\\n".join(f"  - {{i}}" for i in issues)
        # Alert via Dynatrace + ServiceNow
        _send_failure_alert(
            dag_id=DAG_ID, task_id="check_pipeline_status",
            exception=Exception(summary),
            metadata={{
                "date": today,
                "issues_count": len(issues),
                "error_rate": f"{{error_rate:.0%}}",
                "succeeded": succeeded,
                "total": total_checks,
                "issues": [i[:100] for i in issues],
            }},
        )
        raise Exception(summary)
    logger.info(f"{{SYSTEM_NAME}} pipeline complete for {{today}} — {{len(ENTITIES)}} entities, {{len(FDP_MODELS)}} FDP models all succeeded.")


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}}

{dag_id} = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Daily status check for {{SYSTEM_NAME}} pipeline completeness — alerts on gaps or failures",
    schedule="0 23 * * *",
    catchup=False,
    tags=[FILE_PREFIX, "status", "observability"],
)

with {dag_id}:
    PythonOperator(task_id="check_pipeline_status", python_callable=check_pipeline_status)
''')

    return _build_dag_code(imports_section, config_section, task_section)


# =============================================================================
# DAG 5: Error Handling DAG
# =============================================================================

def generate_error_handling_dag(config: Dict[str, Any]) -> str:
    """Generate the error handling DAG as a concrete Python file."""
    system_id = config["system_id"]
    system_id_lower = system_id.lower()
    system_name = config.get("system_name", system_id)
    file_prefix = config.get("file_prefix", system_id_lower)
    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)

    infra = config.get("infrastructure", {})
    datasets = infra.get("datasets", {})
    odp_dataset_template = datasets.get("odp", "odp_{system}")
    buckets = infra.get("buckets", {})
    error_bucket_template = buckets.get("error", "")

    retry_config = config.get("retry_config", {})
    odp_max_retries = retry_config.get("odp", {}).get("max_retries", 3)
    odp_cleanup_on_retry = retry_config.get("odp", {}).get("cleanup_on_retry", True)
    fdp_max_retries = retry_config.get("fdp", {}).get("max_retries", 2)

    dag_id = f"{system_id_lower}_error_handling_dag"
    ingestion_dag_id = f"{system_id_lower}_ingestion_dag"
    transformation_dag_id = f"{system_id_lower}_transformation_dag"

    imports_section = textwrap.dedent('''\
"""
''' + f'{system_name}' + ''' Error Handling DAG

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
''')

    config_section = textwrap.dedent(f'''\
logger = logging.getLogger(__name__)

# =============================================================================
# Baked-in configuration from system.yaml
# =============================================================================
SYSTEM_ID = "{system_id}"
SYSTEM_NAME = "{system_name}"
FILE_PREFIX = "{file_prefix}"
ENTITIES = {entities!r}
FDP_MODELS = {list(fdp_deps.keys())!r}
DAG_ID = "{dag_id}"
INGESTION_DAG_ID = "{ingestion_dag_id}"
TRANSFORMATION_DAG_ID = "{transformation_dag_id}"

# Infrastructure templates
ODP_DATASET_TEMPLATE = "{odp_dataset_template}"
ERROR_BUCKET_TEMPLATE = "{error_bucket_template}"

# Retry config (baked from system.yaml)
ODP_MAX_RETRIES = {odp_max_retries}
ODP_CLEANUP_ON_RETRY = {odp_cleanup_on_retry}
FDP_MAX_RETRIES = {fdp_max_retries}

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

''')

    task_section = textwrap.dedent(f'''\
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
        logger.info(f"No failed jobs for {{SYSTEM_ID}} on {{today}}")
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
                retryable.append({{**job, "stage": stage, "is_fdp": is_fdp}})
            else:
                manual_review.append({{**job, "stage": stage, "exhausted_retries": True}})
        else:
            manual_review.append({{**job, "stage": stage}})

    context["ti"].xcom_push(key="critical_jobs", value=critical)
    context["ti"].xcom_push(key="retryable_jobs", value=retryable)
    context["ti"].xcom_push(key="manual_review_jobs", value=manual_review)

    logger.info(f"Failed jobs: {{len(critical)}} critical, {{len(retryable)}} retryable, {{len(manual_review)}} manual review")

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
        logger.error(f"CRITICAL failure: {{run_id}} entity={{entity}}")
        _send_failure_alert(
            dag_id=DAG_ID, task_id="handle_critical",
            exception=Exception(f"Critical pipeline failure for {{entity}}: {{run_id}}"),
            metadata={{
                "run_id": run_id, "entity": entity,
                "severity": "CRITICAL", "action": "REQUIRES_MANUAL_INTERVENTION",
            }},
        )
        # Publish failure audit
        _publish_audit(run_id, DAG_ID, entity, "error_handling", success=False, error_count=1,
                       metadata={{"severity": "CRITICAL", "action": "alerted"}})
    _push_cloud_monitoring_metric("error_handling_critical", len(critical_jobs), {{"system": SYSTEM_ID}})


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
            odp_table = f"{{project_id}}.{{odp_dataset}}.{{entity}}"
            try:
                deleted = repo.cleanup_partial_load(run_id, odp_table)
                logger.info(f"Cleaned up {{deleted}} partial rows from {{odp_table}} for {{run_id}}")
            except Exception as e:
                logger.warning(f"Cleanup failed for {{run_id}} (non-fatal): {{e}}")

        # Mark as retrying
        repo.mark_retrying(run_id, retry_count=retry_count + 1)

        # Trigger the appropriate DAG
        if is_fdp:
            target_dag = TRANSFORMATION_DAG_ID
            conf = {{"fdp_model": entity, "extract_date": datetime.now(tz=timezone.utc).strftime("%Y%m%d"), "triggered_by": DAG_ID}}
        else:
            target_dag = INGESTION_DAG_ID
            # Reconstruct file metadata for re-ingestion
            full_job = repo.get_job(run_id)
            source_file = full_job.source_files[0] if full_job and full_job.source_files else ""
            conf = {{
                "file_metadata": json.dumps({{
                    "entity": entity,
                    "data_file": source_file,
                    "extract_date": datetime.now(tz=timezone.utc).strftime("%Y%m%d"),
                }}),
                "triggered_by": DAG_ID,
            }}

        try:
            retry_run_id = f"retry_{{run_id}}_{{retry_count + 1}}"
            trigger_dag(dag_id=target_dag, run_id=retry_run_id, conf=conf, replace_microseconds=False)
            logger.info(f"Triggered retry for {{run_id}} → {{target_dag}} (attempt {{retry_count + 1}})")
            retried += 1
        except Exception as e:
            logger.error(f"Failed to trigger retry for {{run_id}}: {{e}}")
            _send_failure_alert(DAG_ID, "handle_retryable", e, {{"run_id": run_id, "entity": entity}})

    logger.info(f"Retried {{retried}}/{{len(retryable_jobs)}} failed jobs")
    _push_cloud_monitoring_metric("error_handling_retried", retried, {{"system": SYSTEM_ID}})


def handle_manual_review(**context):
    """Alert on jobs that need manual review (exhausted retries or config errors)."""
    manual_jobs = context["ti"].xcom_pull(key="manual_review_jobs") or []
    for job in manual_jobs:
        run_id = job["run_id"]
        entity = job["entity_type"]
        stage = job.get("stage", "UNKNOWN")
        exhausted = job.get("exhausted_retries", False)
        reason = "max retries exhausted" if exhausted else f"failure at {{stage}}"
        logger.warning(f"Manual review needed: {{run_id}} entity={{entity}} reason={{reason}}")
        _send_failure_alert(
            dag_id=DAG_ID, task_id="handle_manual_review",
            exception=Exception(f"Manual review needed for {{entity}}: {{reason}}"),
            metadata={{
                "run_id": run_id, "entity": entity, "stage": stage,
                "severity": "WARNING", "action": "REQUIRES_MANUAL_REVIEW",
                "exhausted_retries": exhausted,
            }},
        )
    _push_cloud_monitoring_metric("error_handling_manual_review", len(manual_jobs), {{"system": SYSTEM_ID}})


# =============================================================================
# OTEL + DAG definition
# =============================================================================

_init_otel(DAG_ID)
_log_observability_status(DAG_ID)

default_args = {{
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=1),
}}

{dag_id} = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=f"Monitor and recover failed {{SYSTEM_NAME}} pipeline jobs — runs every 30 min",
    schedule="*/30 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=[FILE_PREFIX, "error", "recovery", "monitoring"],
)

with {dag_id}:
    scan = BranchPythonOperator(task_id="scan_failed_jobs", python_callable=scan_failed_jobs)
    critical = PythonOperator(task_id="handle_critical", python_callable=handle_critical)
    retryable = PythonOperator(task_id="handle_retryable", python_callable=handle_retryable)
    manual = PythonOperator(task_id="handle_manual_review", python_callable=handle_manual_review)
    no_errors = DummyOperator(task_id="no_errors")
    end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    scan >> [critical, retryable, manual, no_errors]
    [critical, retryable, manual, no_errors] >> end
''')

    return _build_dag_code(imports_section, config_section, task_section)


# =============================================================================
# MAIN
# =============================================================================

DAG_GENERATORS = {
    "pubsub_trigger_dag": generate_pubsub_trigger_dag,
    "ingestion_dag": generate_ingestion_dag,
    "transformation_dag": generate_transformation_dag,
    "pipeline_status_dag": generate_pipeline_status_dag,
    "error_handling_dag": generate_error_handling_dag,
}


def generate_all(config: Dict[str, Any], output_dir: Path, dry_run: bool = False) -> List[str]:
    """Generate all five DAG files from config."""
    system_id_lower = config["system_id"].lower()

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    for dag_suffix, generator_fn in DAG_GENERATORS.items():
        filename = f"{system_id_lower}_{dag_suffix}.py"
        filepath = output_dir / filename
        code = generator_fn(config)

        if _should_write(filepath):
            if not dry_run:
                filepath.write_text(code)
            generated.append(filename)
            logger.info(f"  Generated: {filename}")
        else:
            logger.info(f"  Skipped (hand-written): {filename}")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate Airflow DAG files from system.yaml (build-time, not runtime)"
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "system.yaml"),
        help="Path to system.yaml (default: config/system.yaml)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "dags"),
        help="Path to output directory (default: dags/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config_path = Path(args.config)
    output_dir = Path(args.output)

    config = load_config(config_path)
    system_id = config["system_id"]
    entities = _entity_names(config)
    fdp_models = list(_fdp_dependencies(config).keys())

    logger.info(f"Config:  {config_path}")
    logger.info(f"Output:  {output_dir}")
    logger.info(f"Dry run: {args.dry_run}\n")
    logger.info(f"System:    {system_id}")
    logger.info(f"Entities:  {entities}")
    logger.info(f"FDP models: {fdp_models}\n")

    generated = generate_all(config, output_dir, dry_run=args.dry_run)

    logger.info(f"\n{'Would generate' if args.dry_run else 'Generated'} {len(generated)} DAG files:")
    for f in generated:
        logger.info(f"  - {f}")


if __name__ == "__main__":
    main()

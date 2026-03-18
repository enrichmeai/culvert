i"""
Config-driven DAG factory for GCP data pipelines.

Reads system.yaml and generates four Airflow DAGs dynamically:
  1. {system_id}_pubsub_trigger_dag    -- listens for .ok files, triggers ingestion
  2. {system_id}_ingestion_dag         -- runs Dataflow, checks FDP deps, triggers transforms
  3. {system_id}_transformation_dag    -- runs dbt for a specific FDP model
  4. {system_id}_pipeline_status_dag   -- daily observer: alerts if pipeline incomplete

Usage (in any DAG entrypoint file):
    from gcp_pipeline_orchestration.factories.dag_factory import create_dags
    from gcp_pipeline_orchestration.factories.config import load_system_config

    config = load_system_config()
    create_dags(config, globals())
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import json
import logging
import os

from airflow import DAG
from airflow.models import Variable

try:
    # Airflow 3.x
    from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
    from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
    from airflow.providers.standard.operators.bash import BashOperator
    from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
except ImportError:
    # Airflow 2.x
    from airflow.operators.python import PythonOperator, BranchPythonOperator
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator
    from airflow.operators.bash import BashOperator
    try:
        from airflow.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator

from gcp_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator
from gcp_pipeline_core.file_management import HDRTRLParser
from gcp_pipeline_core.audit import AuditTrail, ReconciliationEngine
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob, FailureStage
from gcp_pipeline_core.error_handling import ErrorHandler, GCSErrorStorage

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def _entity_names(config: Dict[str, Any]) -> List[str]:
    return list(config.get("entities", {}).keys())


def _fdp_dependencies(config: Dict[str, Any]) -> Dict[str, List[str]]:
    return {
        model: info["requires"]
        for model, info in config.get("fdp_models", {}).items()
    }


def _resolve_infra(config: Dict[str, Any], project_id: str, env: str) -> Dict[str, str]:
    system = config.get("file_prefix", config.get("system_id", "").lower())
    infra = config.get("infrastructure", {})
    buckets = infra.get("buckets", {})
    pubsub = infra.get("pubsub", {})

    def _fmt(template: str) -> str:
        return template.format(
            project_id=project_id,
            system=system,
            env=env,
            file_prefix=config.get("file_prefix", ""),
        )

    return {
        "landing_bucket": _fmt(buckets.get("landing", "")),
        "archive_bucket": _fmt(buckets.get("archive", "")),
        "error_bucket": _fmt(buckets.get("error", "")),
        "temp_bucket": _fmt(buckets.get("temp", "")),
        "pubsub_topic": _fmt(pubsub.get("topic", "")),
        "pubsub_subscription": _fmt(pubsub.get("subscription", "")),
    }


# =============================================================================
# DAG 1: Pub/Sub Trigger DAG
# =============================================================================

def _build_pubsub_trigger_dag(
    config: Dict[str, Any],
    dag_id: str,
    project_id: str,
    region: str,
    infra: Dict[str, str],
    entities: List[str],
    ingestion_dag_id: str,
) -> DAG:
    system_id = config["system_id"]

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

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f"Listen for {config['system_name']} file arrivals via Pub/Sub and trigger ODP load",
        schedule=None,
        catchup=False,
        max_active_runs=5,
        tags=[config["file_prefix"], "trigger", "pubsub"],
    )

    def parse_pubsub_message(**context) -> Dict[str, Any]:
        messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")
        if not messages:
            logger.warning("No messages received from Pub/Sub")
            return {"status": "no_message"}
        message = messages[0] if isinstance(messages, list) else messages
        
        # Extract file_name and bucket from various message formats
        file_name = ""
        bucket = ""
        
        if isinstance(message, str):
            message_data = json.loads(message)
            file_name = message_data.get("name", "")
            bucket = message_data.get("bucket", "")
        elif isinstance(message, dict):
            # Try direct access first
            file_name = message.get("name", "")
            bucket = message.get("bucket", "")
            
            # If not found, check nested 'message' structure (PubSub format)
            if not file_name:
                nested_msg = message.get("message", {})
                attributes = nested_msg.get("attributes", {}) if isinstance(nested_msg, dict) else {}
                file_name = attributes.get("objectId", "")
                bucket = attributes.get("bucketId", "")
                
                # Also try parsing the data payload
                if not file_name:
                    data = nested_msg.get("data", "") if isinstance(nested_msg, dict) else ""
                    if data:
                        try:
                            import base64
                            if isinstance(data, bytes):
                                data_str = data.decode('utf-8')
                            else:
                                try:
                                    data_str = base64.b64decode(data).decode('utf-8')
                                except Exception:
                                    data_str = data
                            data_json = json.loads(data_str)
                            file_name = data_json.get("name", "")
                            bucket = data_json.get("bucket", "")
                        except Exception as e:
                            logger.debug(f"Could not parse message data: {e}")
        else:
            message_data = message
            file_name = getattr(message_data, "name", "") or ""
            bucket = getattr(message_data, "bucket", "") or ""
            
        logger.info(f"Received notification for: gs://{bucket}/{file_name}")
        
        trigger_suffix = config.get("ok_file_suffix", ".ok")
        if not file_name.endswith(trigger_suffix):
            logger.info(f"Skipping file without {trigger_suffix} suffix: {file_name}")
            return {"status": "skip", "reason": "not_trigger_file"}
            
        entity = None
        for e in entities:
            if e in file_name.lower():
                entity = e
                break
                
        extract_date = None
        base_name = file_name.replace(trigger_suffix, "")
        for part in base_name.split("_"):
            if part.isdigit() and len(part) == 8:
                extract_date = part
                break
        
        # Derive .csv data file path from .ok trigger file
        ok_file = f"gs://{bucket}/{file_name}"
        data_file = f"gs://{bucket}/{file_name.replace(trigger_suffix, '.csv')}"
        
        result = {
            "status": "success",
            "ok_file": ok_file,
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
            if metadata.header.system_id != system_id:
                logger.error(f"System ID mismatch: expected {system_id}, got {metadata.header.system_id}")
                return "handle_validation_error"
            context["ti"].xcom_push(key="hdr_metadata", value={
                "system_id": metadata.header.system_id,
                "entity_type": metadata.header.entity_type,
                "extract_date": str(metadata.header.extract_date),
                "record_count": metadata.trailer.record_count,
            })
            logger.info(f"File validated: {metadata.header.system_id}/{metadata.header.entity_type}")
            run_id = context["run_id"]
            audit = AuditTrail(run_id=run_id, pipeline_name=dag_id, entity_type=file_metadata.get("entity", "unknown"))
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
        client = storage.Client()
        source_bucket = client.bucket(file_metadata.get("bucket"))
        dest_bucket = client.bucket(infra["error_bucket"])
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

    with dag:
        pubsub_subscription = Variable.get(
            f"{config['file_prefix']}_pubsub_subscription",
            default_var=infra["pubsub_subscription"],
        )
        wait_for_file = BasePubSubPullSensor(
            task_id="wait_for_file_notification",
            project_id=project_id,
            subscription=pubsub_subscription,
            max_messages=1,
            filter_extension=config.get("ok_file_suffix", ".ok"),
            metadata_xcom_key="file_metadata",
            poke_interval=30,
            timeout=3600,
        )
        parse_message = PythonOperator(task_id="parse_message", python_callable=parse_pubsub_message)
        validate = BranchPythonOperator(task_id="validate_file", python_callable=validate_file)
        trigger_odp = TriggerDagRunOperator(
            task_id="trigger_odp_load",
            trigger_dag_id=ingestion_dag_id,
            conf={
                "file_metadata": "{{ ti.xcom_pull(task_ids='parse_message') | tojson }}",
                "hdr_metadata": "{{ ti.xcom_pull(task_ids='validate_file', key='hdr_metadata') | tojson }}",
            },
            wait_for_completion=False,
        )
        handle_error = PythonOperator(task_id="handle_validation_error", python_callable=move_to_error_bucket)
        skip = DummyOperator(task_id="skip_processing")
        end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")
        wait_for_file >> parse_message >> validate
        validate >> [trigger_odp, handle_error, skip]
        [trigger_odp, handle_error, skip] >> end

    return dag


# =============================================================================
# DAG 2: Ingestion DAG
# =============================================================================

def _build_ingestion_dag(
    config: Dict[str, Any],
    dag_id: str,
    project_id: str,
    region: str,
    infra: Dict[str, str],
    entities: List[str],
    fdp_deps: Dict[str, List[str]],
    transformation_dag_id: str,
) -> DAG:
    system_id = config["system_id"]
    template_bucket = Variable.get("dataflow_templates_bucket", default_var=infra["temp_bucket"])

    def mark_job_failed(context):
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
                    error_storage = GCSErrorStorage(bucket_name=infra["error_bucket"], prefix=f"error_logs/{run_id}")
                    handler = ErrorHandler(pipeline_name=dag_id, run_id=run_id, error_storage=error_storage)
                    handler.handle_exception(exception, source_file=task_id)
                except Exception as e:
                    logger.warning(f"Error handler storage failed (non-fatal): {e}")
            entity = context["ti"].xcom_pull(key="entity") or "unknown"
            audit = AuditTrail(run_id=run_id, pipeline_name=dag_id, entity_type=entity)
            audit.record_processing_start(source_file="unknown")
            audit.log_entry("FAILURE", f"Task {task_id} failed: {error_message}")
            audit.record_processing_end(success=False)
            logger.error(f"Job {run_id} marked FAILED at stage {stage.value}: {error_code}")

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

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f"Load {config['system_name']} entity data to ODP (BigQuery)",
        schedule=None,
        catchup=False,
        tags=[config["file_prefix"], "odp", "dataflow"],
    )

    def create_job_record(**context):
        conf = context.get("dag_run").conf or {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
        entity = file_metadata.get("entity", "unknown")
        extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        data_file = file_metadata.get("data_file", "")
        run_id = context.get("run_id", f"{config['file_prefix']}_{entity}_{extract_date}")
        extract_date_obj = datetime.strptime(extract_date, "%Y%m%d").date() if extract_date else datetime.now(tz=timezone.utc).date()
        repo = JobControlRepository(project_id=project_id)
        existing = repo.get_entity_status(system_id, extract_date_obj)
        for entry in existing:
            if entry["entity_type"] == entity and entry["status"] == "FAILED":
                old_run_id = entry["run_id"]
                odp_table = f"{project_id}.odp_{config['file_prefix']}.{entity}"
                logger.info(f"Found failed job {old_run_id}. Cleaning up partial data from {odp_table}")
                try:
                    deleted = repo.cleanup_partial_load(old_run_id, odp_table)
                    logger.info(f"Cleaned up {deleted} partial rows from {odp_table} for run {old_run_id}")
                except Exception as e:
                    logger.warning(f"Cleanup of partial load failed (non-fatal): {e}")
                repo.mark_retrying(old_run_id, retry_count=1)
        job = PipelineJob(
            run_id=run_id, system_id=system_id, entity_type=entity,
            extract_date=extract_date_obj, source_files=[data_file],
            started_at=datetime.now(tz=timezone.utc), job_type="ODP_INGESTION",
        )
        repo.create_job(job)
        repo.update_status(run_id, JobStatus.RUNNING)
        logger.info(f"Created job record: {run_id} for entity: {entity}")
        context["ti"].xcom_push(key="run_id", value=run_id)
        context["ti"].xcom_push(key="entity", value=entity)

    def check_ready_fdp_models(**context) -> None:
        conf = context.get("dag_run").conf or {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
        extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        checker = EntityDependencyChecker(project_id=project_id, system_id=system_id, required_entities=entities)
        date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
        loaded = set(checker.get_loaded_entities(date_obj))
        ready_models = [model for model, deps in fdp_deps.items() if set(deps).issubset(loaded)]
        if ready_models:
            logger.info(f"FDP models ready to run: {ready_models} (loaded entities: {loaded})")
        else:
            logger.info(f"No FDP models ready yet. Loaded entities: {loaded}")
        context["ti"].xcom_push(key="ready_fdp_models", value=ready_models)

    def update_job_success(**context):
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
            audit = AuditTrail(run_id=run_id, pipeline_name=dag_id, entity_type=entity or "unknown")
            audit.record_processing_start(source_file=data_file, metadata={"job_type": "ODP_INGESTION", "system_id": system_id})
            audit.record_processing_end(success=True)

    def reconcile_odp_load(**context):
        run_id = context["ti"].xcom_pull(key="run_id")
        entity = context["ti"].xcom_pull(key="entity")
        conf = context.get("dag_run").conf or {}
        hdr_metadata_raw = conf.get("hdr_metadata", {})
        hdr_metadata = json.loads(hdr_metadata_raw) if isinstance(hdr_metadata_raw, str) else hdr_metadata_raw
        expected_count = hdr_metadata.get("record_count") if hdr_metadata else None
        if not expected_count:
            logger.warning(f"No expected record count from HDR/TRL for {entity}. Skipping reconciliation.")
            return
        odp_table = f"{project_id}.odp_{config['file_prefix']}.{entity}"
        error_table = f"{project_id}.odp_{config['file_prefix']}.{entity}_errors"
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
            run_id = f"transform_{model}_{extract_date}"
            logger.info(f"Triggering {transformation_dag_id} for model: {model}")
            trigger_dag(
                dag_id=transformation_dag_id, run_id=run_id,
                conf={"extract_date": extract_date, "fdp_model": model, "triggered_by": dag_id},
                replace_microseconds=False,
            )

    odp_dataset = config.get("infrastructure", {}).get("datasets", {}).get("odp", "odp_{system}")
    odp_dataset_resolved = odp_dataset.format(system=config.get("file_prefix", ""))

    with dag:
        create_job = PythonOperator(task_id="create_job_record", python_callable=create_job_record)
        run_dataflow = BaseDataflowOperator(
            task_id="run_dataflow_pipeline",
            pipeline_name=f"{config['file_prefix']}-odp-load",
            project_id=project_id,
            region=region,
            source_type="gcs",
            processing_mode="batch",
            input_path="{{ dag_run.conf.file_metadata.data_file }}",
            output_table=f"{project_id}:{odp_dataset_resolved}.{{{{ dag_run.conf.file_metadata.entity }}}}",
            template_path=f"gs://{template_bucket}/templates/{config['file_prefix']}_pipeline.json",
            use_template=True,
            additional_params={"run_id": '{{ ti.xcom_pull(key="run_id") }}'},
        )
        mark_success = PythonOperator(task_id="update_job_success", python_callable=update_job_success)
        reconcile = PythonOperator(task_id="reconcile_odp_load", python_callable=reconcile_odp_load)
        check_deps = PythonOperator(task_id="check_ready_fdp_models", python_callable=check_ready_fdp_models)
        trigger_transforms = PythonOperator(task_id="trigger_ready_transforms", python_callable=trigger_ready_transforms)
        end = DummyOperator(task_id="end")
        create_job >> run_dataflow >> mark_success >> reconcile >> check_deps >> trigger_transforms >> end

    return dag


# =============================================================================
# DAG 3: Transformation DAG
# =============================================================================

def _build_transformation_dag(
    config: Dict[str, Any],
    dag_id: str,
    project_id: str,
    region: str,
    entities: List[str],
    fdp_deps: Dict[str, List[str]],
    infra: Dict[str, str],
) -> DAG:
    system_id = config["system_id"]
    dbt_project_path = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")

    def mark_fdp_job_failed(context):
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
                    error_storage = GCSErrorStorage(bucket_name=infra["error_bucket"], prefix=f"error_logs/{run_id}")
                    handler = ErrorHandler(pipeline_name=dag_id, run_id=run_id, error_storage=error_storage)
                    handler.handle_exception(exception, source_file=task_id)
                except Exception as e:
                    logger.warning(f"Error handler storage failed (non-fatal): {e}")
            conf = context.get("dag_run").conf or {}
            fdp_model = conf.get("fdp_model", "unknown")
            audit = AuditTrail(run_id=run_id, pipeline_name=dag_id, entity_type=fdp_model)
            audit.record_processing_start(source_file=f"odp_{config['file_prefix']}.*")
            audit.log_entry("FAILURE", f"Task {task_id} failed: {error_message}")
            audit.record_processing_end(success=False)
            logger.error(f"FDP job {run_id} marked FAILED at stage {stage.value}: {error_code}")

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

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f"Transform {config['system_name']} ODP to FDP — runs per-model based on granular dependencies",
        schedule=None,
        catchup=False,
        tags=[config["file_prefix"], "fdp", "dbt", "transformation"],
    )

    def verify_model_dependencies(**context) -> str:
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "")
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        if not fdp_model or fdp_model not in fdp_deps:
            logger.error(f"Unknown or missing FDP model: '{fdp_model}'. Expected one of: {list(fdp_deps.keys())}")
            return "handle_dependency_failure"
        required_entities = fdp_deps[fdp_model]
        checker = EntityDependencyChecker(project_id=project_id, system_id=system_id, required_entities=required_entities)
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
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "")
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        run_id = context.get("run_id", f"transform_{fdp_model}_{extract_date}")
        date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
        repo = JobControlRepository(project_id=project_id)
        required_entities = fdp_deps.get(fdp_model, [])
        parent_statuses = repo.get_entity_status(system_id, date_obj)
        parent_run_ids = [
            s["run_id"] for s in parent_statuses
            if s["entity_type"] in required_entities and s["status"] == "SUCCESS"
        ]
        job = PipelineJob(
            run_id=run_id, system_id=system_id, entity_type=fdp_model,
            extract_date=date_obj, started_at=datetime.now(tz=timezone.utc),
            job_type="FDP_TRANSFORMATION", dbt_model_name=fdp_model, parent_run_ids=parent_run_ids,
        )
        repo.create_job(job)
        repo.update_status(run_id, JobStatus.RUNNING)
        logger.info(f"Created FDP job record: {run_id} for model: {fdp_model}, parents: {parent_run_ids}")
        context["ti"].xcom_push(key="fdp_run_id", value=run_id)

    def handle_dependency_failure(**context):
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "unknown")
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        run_id = context.get("run_id", f"transform_{fdp_model}_{extract_date}")
        missing = context["ti"].xcom_pull(key="missing_entities") or []
        date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
        repo = JobControlRepository(project_id=project_id)
        job = PipelineJob(
            run_id=run_id, system_id=system_id, entity_type=fdp_model,
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
        run_id = context["ti"].xcom_pull(key="fdp_run_id")
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "unknown")
        if run_id:
            repo = JobControlRepository(project_id=project_id)
            repo.update_status(run_id, JobStatus.SUCCESS)
            logger.info(f"FDP job {run_id} marked as SUCCESS")
            audit = AuditTrail(run_id=run_id, pipeline_name=dag_id, entity_type=fdp_model)
            audit.record_processing_start(
                source_file=f"odp_{config['file_prefix']}.*",
                metadata={"job_type": "FDP_TRANSFORMATION", "system_id": system_id, "dbt_model": fdp_model},
            )
            audit.record_processing_end(success=True)

    def reconcile_fdp_model_output(**context):
        run_id = context["ti"].xcom_pull(key="fdp_run_id")
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "")
        fdp_dataset = config.get("infrastructure", {}).get("datasets", {}).get("fdp", "fdp_{system}")
        fdp_dataset_resolved = fdp_dataset.format(system=config.get("file_prefix", ""))
        fdp_table = f"{project_id}.{fdp_dataset_resolved}.{fdp_model}"
        required_entities = fdp_deps.get(fdp_model, [])
        odp_dataset = config.get("infrastructure", {}).get("datasets", {}).get("odp", "odp_{system}")
        odp_dataset_resolved = odp_dataset.format(system=config.get("file_prefix", ""))
        source_tables = [f"{project_id}.{odp_dataset_resolved}.{e}" for e in required_entities]
        model_info = config.get("fdp_models", {}).get(fdp_model, {})
        join_type = "map" if model_info.get("type") == "map" else "inner"
        engine = ReconciliationEngine(entity_type=fdp_model, run_id=run_id, project_id=project_id)
        result = engine.reconcile_fdp_model(
            model_name=fdp_model, source_tables=source_tables,
            destination_table=fdp_table, join_type=join_type,
        )
        if not result.is_reconciled:
            raise Exception(f"FDP reconciliation MISMATCH for {fdp_model}: {result.message}")
        logger.info(f"FDP reconciliation passed for {fdp_model}: {result.actual_count} rows")

    with dag:
        verify = BranchPythonOperator(task_id="verify_model_dependencies", python_callable=verify_model_dependencies)
        create_fdp_job = PythonOperator(task_id="create_fdp_job_record", python_callable=create_fdp_job_record)
        staging = BashOperator(
            task_id="run_dbt_staging",
            bash_command=f"cd {dbt_project_path} && dbt run --select staging --vars '{{\"extract_date\": \"{{{{ ds_nodash }}}}\"}}' --target prod",
        )
        fdp = BashOperator(
            task_id="run_dbt_fdp",
            bash_command=f"cd {dbt_project_path} && dbt run --select '{{{{ dag_run.conf.fdp_model }}}}' --vars '{{\"extract_date\": \"{{{{ ds_nodash }}}}\"}}' --target prod",
        )
        tests = BashOperator(
            task_id="run_dbt_tests",
            bash_command=f"cd {dbt_project_path} && dbt test --select '{{{{ dag_run.conf.fdp_model }}}}' --target prod",
        )
        reconcile_fdp = PythonOperator(task_id="reconcile_fdp_model", python_callable=reconcile_fdp_model_output)
        mark_success = PythonOperator(task_id="mark_fdp_success", python_callable=update_fdp_job_success)
        dep_failure = PythonOperator(task_id="handle_dependency_failure", python_callable=handle_dependency_failure)
        end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")
        verify >> [create_fdp_job, dep_failure]
        create_fdp_job >> staging >> fdp >> tests >> reconcile_fdp >> mark_success >> end
        dep_failure >> end

    return dag


# =============================================================================
# DAG 4: Pipeline Status DAG (observer — no triggering)
# =============================================================================

def _build_pipeline_status_dag(
    config: Dict[str, Any],
    dag_id: str,
    project_id: str,
    entities: List[str],
    fdp_deps: Dict[str, List[str]],
) -> DAG:
    """
    Daily observer DAG — queries job_control at end of day and alerts if
    any entity or FDP model is missing or failed. Does not trigger anything.
    """
    default_args = {
        "owner": "data-engineering",
        "depends_on_past": False,
        "start_date": datetime(2026, 1, 1),
        "email_on_failure": True,
        "email_on_retry": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f"Daily status check for {config['system_name']} pipeline completeness — alerts on gaps or failures",
        schedule="0 23 * * *",
        catchup=False,
        tags=[config["file_prefix"], "status", "observability"],
    )

    system_id = config["system_id"]

    def check_pipeline_status(**context):
        today = context["ds_nodash"]
        date_obj = datetime.strptime(today, "%Y%m%d").date()
        repo = JobControlRepository(project_id=project_id)
        statuses = repo.get_entity_status(system_id, date_obj)
        status_map = {s["entity_type"]: s["status"] for s in statuses}
        issues = []
        for entity in entities:
            status = status_map.get(entity)
            if status == "SUCCESS":
                logger.info(f"  ODP {entity}: SUCCESS")
            elif status == "FAILED":
                issues.append(f"ODP {entity}: FAILED")
                logger.error(f"  ODP {entity}: FAILED")
            else:
                issues.append(f"ODP {entity}: NOT LOADED (status={status})")
                logger.warning(f"  ODP {entity}: NOT LOADED")
        for model in fdp_deps:
            status = status_map.get(model)
            if status == "SUCCESS":
                logger.info(f"  FDP {model}: SUCCESS")
            elif status == "FAILED":
                issues.append(f"FDP {model}: FAILED")
                logger.error(f"  FDP {model}: FAILED")
            else:
                issues.append(f"FDP {model}: NOT RUN (status={status})")
                logger.warning(f"  FDP {model}: NOT RUN")
        if issues:
            summary = f"{config['system_name']} pipeline incomplete for {today}:\n" + "\n".join(f"  - {i}" for i in issues)
            raise Exception(summary)
        logger.info(f"{config['system_name']} pipeline complete for {today} — {len(entities)} entities, {len(fdp_deps)} FDP models all succeeded.")

    with dag:
        PythonOperator(task_id="check_pipeline_status", python_callable=check_pipeline_status)

    return dag


# =============================================================================
# Public API
# =============================================================================

def create_dags(config: Dict[str, Any], global_ns: Dict[str, Any]) -> None:
    """
    Generate all four paved path DAGs from a system config and inject them
    into *global_ns* so Airflow's DagBag discovers them.

    Parameters
    ----------
    config : dict
        Parsed system.yaml (as returned by ``load_system_config``).
    global_ns : dict
        The caller's ``globals()`` dict.
    """
    system_id = config["system_id"].lower()

    project_id = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
    region = Variable.get("gcp_region", default_var="europe-west2")
    env = Variable.get("environment", default_var="int")

    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)
    infra = _resolve_infra(config, project_id, env)

    trigger_dag_id = f"{system_id}_pubsub_trigger_dag"
    ingestion_dag_id = f"{system_id}_ingestion_dag"
    transformation_dag_id = f"{system_id}_transformation_dag"
    status_dag_id = f"{system_id}_pipeline_status_dag"

    global_ns[trigger_dag_id] = _build_pubsub_trigger_dag(
        config=config, dag_id=trigger_dag_id, project_id=project_id,
        region=region, infra=infra, entities=entities, ingestion_dag_id=ingestion_dag_id,
    )
    global_ns[ingestion_dag_id] = _build_ingestion_dag(
        config=config, dag_id=ingestion_dag_id, project_id=project_id,
        region=region, infra=infra, entities=entities, fdp_deps=fdp_deps,
        transformation_dag_id=transformation_dag_id,
    )
    global_ns[transformation_dag_id] = _build_transformation_dag(
        config=config, dag_id=transformation_dag_id, project_id=project_id,
        region=region, entities=entities, fdp_deps=fdp_deps, infra=infra,
    )
    global_ns[status_dag_id] = _build_pipeline_status_dag(
        config=config, dag_id=status_dag_id, project_id=project_id,
        entities=entities, fdp_deps=fdp_deps,
    )


__all__ = ['create_dags']

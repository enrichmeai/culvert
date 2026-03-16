"""
Config-driven DAG factory for the data-pipeline-orchestrator.

Reads system.yaml and generates three Airflow DAGs dynamically:
  1. {system_id}_pubsub_trigger_dag  -- listens for .ok files, triggers ingestion
  2. {system_id}_ingestion_dag       -- runs Dataflow, checks FDP deps, triggers transforms
  3. {system_id}_transformation_dag  -- runs dbt for a specific FDP model

Usage (in any DAG file):
    from dag_factory import create_dags
    from config.config_loader import load_system_config

    config = load_system_config()
    create_dags(config, globals())
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse
import json
import logging
import os

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.models import Variable

from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor, PubSubCompletionSensor
from gcp_pipeline_orchestration import EntityDependencyChecker, BaseDataflowOperator
from gcp_pipeline_core.file_management import HDRTRLParser
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers -- extract config sections into simple Python structures
# =============================================================================

def _entity_names(config: Dict[str, Any]) -> List[str]:
    """Return the list of entity names from config."""
    return list(config.get("entities", {}).keys())


def _fdp_dependencies(config: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return {fdp_model: [required_entity, ...]} from config."""
    return {
        model: info["requires"]
        for model, info in config.get("fdp_models", {}).items()
    }


def _resolve_infra(config: Dict[str, Any], project_id: str, env: str) -> Dict[str, str]:
    """
    Resolve infrastructure template strings from config.

    Returns a flat dict with keys like 'landing_bucket', 'pubsub_subscription', etc.
    """
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
    """Build the Pub/Sub trigger DAG."""
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
        schedule_interval=None,
        catchup=False,
        max_active_runs=5,
        tags=[config["file_prefix"], "trigger", "pubsub"],
    )

    # -- callable factories (close over config values) -----------------------

    def parse_pubsub_message(**context) -> Dict[str, Any]:
        """Parse the Pub/Sub message to extract file metadata."""
        messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")

        if not messages:
            logger.warning("No messages received from Pub/Sub")
            return {"status": "no_message"}

        message = messages[0] if isinstance(messages, list) else messages

        if isinstance(message, str):
            message_data = json.loads(message)
        else:
            message_data = message

        file_name = message_data.get("name", "")
        bucket = message_data.get("bucket", "")

        logger.info(f"Received notification for: gs://{bucket}/{file_name}")

        if not file_name.endswith(config.get("ok_file_suffix", ".ok")):
            logger.info(f"Skipping non-.ok file: {file_name}")
            return {"status": "skip", "reason": "not_ok_file"}

        entity = None
        for e in entities:
            if e in file_name.lower():
                entity = e
                break

        extract_date = None
        base_name = file_name.replace(".ok", "")
        parts = base_name.split("_")
        for part in parts:
            if part.isdigit() and len(part) == 8:
                extract_date = part
                break

        result = {
            "status": "success",
            "ok_file": f"gs://{bucket}/{file_name}",
            "data_file": f"gs://{bucket}/{file_name.replace('.ok', '.csv')}",
            "entity": entity,
            "extract_date": extract_date,
            "bucket": bucket,
        }

        logger.info(f"Parsed file metadata: {result}")
        context["ti"].xcom_push(key="file_metadata", value=result)
        return result

    def validate_file(**context) -> str:
        """
        Validate the data file using HDRTRLParser.

        Returns branch task ID:
        - 'trigger_odp_load' if valid
        - 'handle_validation_error' if invalid
        - 'skip_processing' if not a valid trigger
        """
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
                logger.error(
                    f"System ID mismatch: expected {system_id}, got {metadata.header.system_id}"
                )
                return "handle_validation_error"

            context["ti"].xcom_push(key="hdr_metadata", value={
                "system_id": metadata.header.system_id,
                "entity_type": metadata.header.entity_type,
                "extract_date": str(metadata.header.extract_date),
                "record_count": metadata.trailer.record_count,
            })

            logger.info(f"File validated: {metadata.header.system_id}/{metadata.header.entity_type}")

            run_id = context["run_id"]
            audit = AuditTrail(
                run_id=run_id,
                pipeline_name=dag_id,
                entity_type=file_metadata.get("entity", "unknown"),
            )
            audit.record_processing_start(source_file=data_file)
            audit.log_entry(
                status="INFO",
                message=f"File validated: record_count={metadata.trailer.record_count}",
            )

            return "trigger_odp_load"

        except Exception as e:
            logger.error(f"File validation failed: {e}")
            return "handle_validation_error"

    def move_to_error_bucket(**context):
        """Move invalid file to error bucket."""
        from google.cloud import storage

        file_metadata = context["ti"].xcom_pull(task_ids="parse_message")

        if not file_metadata or file_metadata.get("status") != "success":
            return

        client = storage.Client()
        source_bucket = client.bucket(file_metadata.get("bucket"))
        error_bucket_name = infra["error_bucket"]
        dest_bucket = client.bucket(error_bucket_name)

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

    # -- tasks ---------------------------------------------------------------

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

        parse_message = PythonOperator(
            task_id="parse_message",
            python_callable=parse_pubsub_message,
        )

        validate = BranchPythonOperator(
            task_id="validate_file",
            python_callable=validate_file,
        )

        trigger_odp = TriggerDagRunOperator(
            task_id="trigger_odp_load",
            trigger_dag_id=ingestion_dag_id,
            conf={"file_metadata": "{{ ti.xcom_pull(task_ids='parse_message') | tojson }}"},
            wait_for_completion=False,
        )

        handle_error = PythonOperator(
            task_id="handle_validation_error",
            python_callable=move_to_error_bucket,
        )

        skip = DummyOperator(
            task_id="skip_processing",
        )

        end = DummyOperator(
            task_id="end",
            trigger_rule="none_failed_min_one_success",
        )

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
    """Build the data ingestion (Dataflow) DAG."""
    system_id = config["system_id"]
    template_bucket = Variable.get(
        "dataflow_templates_bucket",
        default_var=infra["temp_bucket"],
    )

    def mark_job_failed(context):
        """On-failure callback -- marks job as FAILED in job control."""
        run_id = context["ti"].xcom_pull(key="run_id")
        task_id = context["task_instance"].task_id

        if run_id:
            repo = JobControlRepository(project_id=project_id)
            repo.update_status(run_id, JobStatus.FAILED)
            logger.error(f"Job {run_id} marked as FAILED -- failed task: {task_id}")

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
        schedule_interval=None,
        catchup=False,
        tags=[config["file_prefix"], "odp", "dataflow"],
    )

    # -- callables -----------------------------------------------------------

    def create_job_record(**context):
        """Create job control record before processing."""
        conf = context.get("dag_run").conf or {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw

        entity = file_metadata.get("entity", "unknown")
        extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        data_file = file_metadata.get("data_file", "")
        run_id = context.get("run_id", f"{config['file_prefix']}_{entity}_{extract_date}")

        repo = JobControlRepository(project_id=project_id)
        job = PipelineJob(
            run_id=run_id,
            system_id=system_id,
            entity_type=entity,
            extract_date=datetime.strptime(extract_date, "%Y%m%d").date() if extract_date else datetime.now(tz=timezone.utc).date(),
            source_files=[data_file],
            started_at=datetime.now(tz=timezone.utc),
        )
        repo.create_job(job)
        repo.update_status(run_id, JobStatus.RUNNING)

        logger.info(f"Created job record: {run_id} for entity: {entity}")
        context["ti"].xcom_push(key="run_id", value=run_id)
        context["ti"].xcom_push(key="entity", value=entity)

    def check_ready_fdp_models(**context) -> None:
        """
        Check which FDP models can now run based on loaded entities.

        After each entity load, queries job_control for all loaded entities
        and determines which FDP models have all their dependencies satisfied.
        """
        conf = context.get("dag_run").conf or {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = json.loads(file_metadata_raw) if isinstance(file_metadata_raw, str) else file_metadata_raw
        extract_date = file_metadata.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))

        checker = EntityDependencyChecker(
            project_id=project_id,
            system_id=system_id,
            required_entities=entities,
        )

        date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
        loaded = set(checker.get_loaded_entities(date_obj))

        ready_models = []
        for model, deps in fdp_deps.items():
            if set(deps).issubset(loaded):
                ready_models.append(model)

        if ready_models:
            logger.info(f"FDP models ready to run: {ready_models} (loaded entities: {loaded})")
        else:
            logger.info(f"No FDP models ready yet. Loaded entities: {loaded}")

        context["ti"].xcom_push(key="ready_fdp_models", value=ready_models)

    def update_job_success(**context):
        """Update job control status to success."""
        run_id = context["ti"].xcom_pull(key="run_id")

        if run_id:
            repo = JobControlRepository(project_id=project_id)
            repo.update_status(run_id, JobStatus.SUCCESS)
            logger.info(f"Job {run_id} marked as SUCCESS")

    def trigger_ready_transforms(**context):
        """
        Trigger transformation_dag for each FDP model that is ready.
        """
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
                dag_id=transformation_dag_id,
                run_id=run_id,
                conf={
                    "extract_date": extract_date,
                    "fdp_model": model,
                    "triggered_by": dag_id,
                },
                replace_microseconds=False,
            )

    # -- tasks ---------------------------------------------------------------

    odp_dataset = config.get("infrastructure", {}).get("datasets", {}).get("odp", "odp_{system}")
    odp_dataset_resolved = odp_dataset.format(system=config.get("file_prefix", ""))

    with dag:
        create_job = PythonOperator(
            task_id="create_job_record",
            python_callable=create_job_record,
        )

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
            additional_params={
                "run_id": '{{ ti.xcom_pull(key="run_id") }}',
            },
        )

        mark_success = PythonOperator(
            task_id="update_job_success",
            python_callable=update_job_success,
        )

        check_deps = PythonOperator(
            task_id="check_ready_fdp_models",
            python_callable=check_ready_fdp_models,
        )

        trigger_transforms = PythonOperator(
            task_id="trigger_ready_transforms",
            python_callable=trigger_ready_transforms,
        )

        end = DummyOperator(
            task_id="end",
        )

        create_job >> run_dataflow >> mark_success >> check_deps >> trigger_transforms >> end

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
) -> DAG:
    """Build the dbt transformation DAG."""
    system_id = config["system_id"]
    dbt_project_path = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")

    default_args = {
        "owner": "data-engineering",
        "depends_on_past": False,
        "email_on_failure": True,
        "email_on_retry": False,
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
        "start_date": datetime(2026, 1, 1),
    }

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f"Transform {config['system_name']} ODP to FDP -- runs per-model based on granular dependencies",
        schedule_interval=None,
        catchup=False,
        tags=[config["file_prefix"], "fdp", "dbt", "transformation"],
    )

    # -- callables -----------------------------------------------------------

    def verify_model_dependencies(**context) -> str:
        """
        Verify that the requested FDP model's ODP dependencies are loaded.

        Returns branch task ID:
        - 'run_dbt_staging' if dependencies are satisfied
        - 'skip_transformation' if not
        """
        conf = context.get("dag_run").conf or {}
        fdp_model = conf.get("fdp_model", "")
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))

        if not fdp_model or fdp_model not in fdp_deps:
            logger.error(
                f"Unknown or missing FDP model: '{fdp_model}'. "
                f"Expected one of: {list(fdp_deps.keys())}"
            )
            return "skip_transformation"

        required_entities = fdp_deps[fdp_model]

        checker = EntityDependencyChecker(
            project_id=project_id,
            system_id=system_id,
            required_entities=required_entities,
        )

        date_obj = datetime.strptime(extract_date, "%Y%m%d").date()

        if checker.all_entities_loaded(date_obj):
            logger.info(f"Dependencies satisfied for {fdp_model}: {required_entities}. Proceeding.")
            context["ti"].xcom_push(key="fdp_model", value=fdp_model)
            context["ti"].xcom_push(key="required_entities", value=required_entities)
            return "run_dbt_staging"
        else:
            missing = checker.get_missing_entities(date_obj)
            logger.warning(f"Cannot run {fdp_model}. Missing entities: {missing}")
            return "skip_transformation"

    def update_job_status(status: str, **context):
        """Update job control status after transformation."""
        run_id = context.get("run_id", "unknown")

        repo = JobControlRepository(project_id=project_id)

        if status == "success":
            repo.update_status(run_id, JobStatus.SUCCESS)
            logger.info(f"Job {run_id} marked as SUCCESS")
        else:
            repo.update_status(run_id, JobStatus.FAILED)
            logger.error(f"Job {run_id} marked as FAILED")

    # -- tasks ---------------------------------------------------------------

    with dag:
        verify = BranchPythonOperator(
            task_id="verify_model_dependencies",
            python_callable=verify_model_dependencies,
        )

        staging = BashOperator(
            task_id="run_dbt_staging",
            bash_command=f'''
                cd {dbt_project_path} && \
                dbt run --select staging --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
            ''',
        )

        fdp = BashOperator(
            task_id="run_dbt_fdp",
            bash_command=f'''
                cd {dbt_project_path} && \
                dbt run --select "{{{{ dag_run.conf.fdp_model }}}}" \
                    --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
            ''',
        )

        tests = BashOperator(
            task_id="run_dbt_tests",
            bash_command=f'''
                cd {dbt_project_path} && \
                dbt test --select "{{{{ dag_run.conf.fdp_model }}}}" --target prod
            ''',
        )

        mark_success = PythonOperator(
            task_id="mark_success",
            python_callable=update_job_status,
            op_kwargs={"status": "success"},
        )

        skip = DummyOperator(
            task_id="skip_transformation",
        )

        end = DummyOperator(
            task_id="end",
            trigger_rule="none_failed_min_one_success",
        )

        verify >> [staging, skip]
        staging >> fdp >> tests >> mark_success >> end
        skip >> end

    return dag


# =============================================================================
# Public API
# =============================================================================

def create_dags(config: Dict[str, Any], global_ns: Dict[str, Any]) -> None:
    """
    Generate all three DAGs from a system config and inject them into *global_ns*.

    Parameters
    ----------
    config : dict
        Parsed system.yaml (as returned by ``load_system_config``).
    global_ns : dict
        The caller's ``globals()`` dict.  DAG objects are written here so
        that Airflow's DagBag discovers them.
    """
    system_id = config["system_id"].lower()

    # Shared GCP context
    project_id = Variable.get(
        "gcp_project_id",
        default_var=os.environ.get("GCP_PROJECT_ID", ""),
    )
    region = Variable.get("gcp_region", default_var="europe-west2")
    env = Variable.get("environment", default_var="int")

    entities = _entity_names(config)
    fdp_deps = _fdp_dependencies(config)
    infra = _resolve_infra(config, project_id, env)

    # Deterministic DAG IDs
    trigger_dag_id = f"{system_id}_pubsub_trigger_dag"
    ingestion_dag_id = f"{system_id}_ingestion_dag"
    transformation_dag_id = f"{system_id}_transformation_dag"

    # Build all three DAGs
    trigger_dag = _build_pubsub_trigger_dag(
        config=config,
        dag_id=trigger_dag_id,
        project_id=project_id,
        region=region,
        infra=infra,
        entities=entities,
        ingestion_dag_id=ingestion_dag_id,
    )

    ingestion_dag = _build_ingestion_dag(
        config=config,
        dag_id=ingestion_dag_id,
        project_id=project_id,
        region=region,
        infra=infra,
        entities=entities,
        fdp_deps=fdp_deps,
        transformation_dag_id=transformation_dag_id,
    )

    transformation_dag = _build_transformation_dag(
        config=config,
        dag_id=transformation_dag_id,
        project_id=project_id,
        region=region,
        entities=entities,
        fdp_deps=fdp_deps,
    )

    # Inject into caller's module namespace so Airflow discovers them
    global_ns[trigger_dag_id] = trigger_dag
    global_ns[ingestion_dag_id] = ingestion_dag
    global_ns[transformation_dag_id] = transformation_dag

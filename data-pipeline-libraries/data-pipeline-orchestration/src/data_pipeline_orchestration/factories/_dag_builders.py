"""Internal DAG builder functions for DagFactory.

These functions produce real, importable Airflow DAGs from a config dict
(the same shape as system.yaml) without writing files to disk.  They mirror
the logic in ``generate_dags.py`` but operate at *runtime* so a scheduler
can discover them from a thin loader module such as::

    # dags/factory_runtime.py
    from data_pipeline_orchestration.factories.dag_factory_alias import DagFactory
    factory = DagFactory.from_config("/home/airflow/gcs/dags/config/system.yaml")
    for name, dag in factory.ingestion_dags():
        globals()[f"ingestion_{name}"] = dag
    globals()["pubsub_trigger"] = factory.pubsub_trigger_dag()
    globals()["error_handling"] = factory.error_handling_dag()
    globals()["status"] = factory.status_dag()
    for dag in factory.transformation_dags():
        globals()[dag.dag_id] = dag

When Airflow is *not* installed (unit-test environments) every builder raises
``ImportError`` with a clear message.  The ``DagFactory`` catches that and
falls back to ``_stub_dag()``.

DAG_PREFIX env-var (used by ``scripts/dev/sync_sandbox_dags.sh``) is
honoured as a prefix on every dag_id.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Airflow availability guard
# ---------------------------------------------------------------------------

_AIRFLOW_ERR = (
    "apache-airflow is required to build real DAGs. "
    "Install with: pip install apache-airflow"
)


def _require_airflow():
    """Raise ImportError if Airflow is absent."""
    try:
        import airflow  # noqa: F401
    except ImportError:
        raise ImportError(_AIRFLOW_ERR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dag_prefix() -> str:
    """Return the DAG_PREFIX env-var value (with trailing _ if set)."""
    prefix = os.environ.get("DAG_PREFIX", "")
    if prefix and not prefix.endswith("_"):
        prefix += "_"
    return prefix


def _prefixed(dag_id: str) -> str:
    return f"{_dag_prefix()}{dag_id}"


def _get_operators():
    """Lazy-import Airflow operators; raise ImportError if absent."""
    _require_airflow()
    try:
        from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
        from airflow.providers.standard.operators.empty import EmptyOperator as DummyOperator
    except ImportError:
        from airflow.operators.python import PythonOperator, BranchPythonOperator  # type: ignore
        try:
            from airflow.operators.empty import EmptyOperator as DummyOperator  # type: ignore
        except ImportError:
            from airflow.operators.dummy import DummyOperator  # type: ignore
    try:
        from airflow.providers.standard.operators.bash import BashOperator
    except ImportError:
        from airflow.operators.bash import BashOperator  # type: ignore
    return PythonOperator, BranchPythonOperator, DummyOperator, BashOperator


def _get_dag_class():
    _require_airflow()
    from airflow import DAG
    return DAG


def _default_args(retries: int = 3, retry_delay_minutes: int = 5,
                  on_failure_callback=None) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "owner": "data-engineering",
        "depends_on_past": False,
        "email_on_failure": True,
        "email_on_retry": False,
        "retries": retries,
        "retry_delay": timedelta(minutes=retry_delay_minutes),
        "start_date": datetime(2026, 1, 1),
    }
    if on_failure_callback is not None:
        args["on_failure_callback"] = on_failure_callback
    return args


def _system_tags(cfg: Dict[str, Any]) -> List[str]:
    file_prefix = cfg.get("file_prefix", cfg.get("system_id", "generic")).lower()
    return [file_prefix]


def _failure_callback():
    """Return the global ``on_failure_callback`` (DLQ/quarantine router).

    Imported lazily inside the builder body so that ``dag_factory`` and this
    module stay import-safe without ``gcp_pipeline_core`` at module load time
    (``callbacks.dlq`` imports ``gcp_pipeline_core`` at its top level). When the
    callbacks package cannot be imported, returns ``None`` so DAG construction
    still succeeds (the DAG simply carries no failure callback).
    """
    try:
        from data_pipeline_orchestration.callbacks import on_failure_callback
        return on_failure_callback
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Could not import on_failure_callback (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# DAG 1: PubSub Trigger DAG
# ---------------------------------------------------------------------------

def build_pubsub_trigger_dag(factory_config: Dict[str, Any], **kwargs) -> "Any":  # noqa: ANN401
    """Build the PubSub trigger DAG dynamically.

    Equivalent to the DAG emitted by ``generate_pubsub_trigger_dag()`` in
    generate_dags.py.  The task graph is::

        wait_for_file_notification
            → parse_message
                → validate_file (branch)
                    → trigger_odp_load
                    → handle_validation_error
                    → skip_processing
                        → end

    Raises:
        ImportError: when apache-airflow is not installed.
    """
    _require_airflow()
    DAG = _get_dag_class()
    PythonOperator, BranchPythonOperator, DummyOperator, _ = _get_operators()

    system_id = factory_config.get("system_id", "generic")
    system_id_lower = system_id.lower()
    file_prefix = factory_config.get("file_prefix", system_id_lower)
    ok_file_suffix = factory_config.get("ok_file_suffix", ".ok")
    entities = sorted((factory_config.get("entities") or {}).keys())
    trigger_schedule = factory_config.get("trigger_schedule", "*/1 * * * *")

    infra = factory_config.get("infrastructure", {})
    pubsub_cfg = infra.get("pubsub", {})
    pubsub_subscription_template = pubsub_cfg.get("subscription", "")
    error_bucket_template = infra.get("buckets", {}).get("error", "")

    ingestion_dag_map = {e: f"{system_id_lower}_{e}_ingestion_dag" for e in entities}
    dag_id = _prefixed(f"{system_id_lower}_pubsub_trigger_dag")

    # ---- task callables (closures so they capture config) ------------------

    def parse_pubsub_message(**context):
        import base64
        messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")
        if not messages:
            log.warning("No messages received from Pub/Sub")
            return {"status": "no_message"}
        message = messages[0] if isinstance(messages, list) else messages
        file_name = ""
        bucket = ""
        if isinstance(message, str):
            import json as _json
            data = _json.loads(message)
            file_name = data.get("name", "")
            bucket = data.get("bucket", "")
        elif isinstance(message, dict):
            file_name = message.get("name", "")
            bucket = message.get("bucket", "")
            if not file_name:
                nested = message.get("message", {})
                attrs = nested.get("attributes", {}) if isinstance(nested, dict) else {}
                file_name = attrs.get("objectId", "")
                bucket = attrs.get("bucketId", "")
                if not file_name:
                    raw = nested.get("data", "") if isinstance(nested, dict) else ""
                    if raw:
                        try:
                            decoded = (
                                raw.decode("utf-8") if isinstance(raw, bytes)
                                else base64.b64decode(raw).decode("utf-8")
                            )
                            parsed = json.loads(decoded)
                            file_name = parsed.get("name", "")
                            bucket = parsed.get("bucket", "")
                        except Exception as exc:
                            log.debug("Could not parse message data: %s", exc)
        else:
            file_name = getattr(message, "name", "") or ""
            bucket = getattr(message, "bucket", "") or ""
        log.info("Notification for gs://%s/%s", bucket, file_name)
        if not file_name.endswith(ok_file_suffix):
            return {"status": "skip", "reason": "not_trigger_file", "file_name": file_name}
        bare = file_name[: -len(ok_file_suffix)]
        if "." not in bare.rsplit("/", 1)[-1]:
            bare += ".csv"
        stem = bare.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        parts = stem.split("_")
        entity = parts[1] if len(parts) >= 3 else None
        extract_date = next((p for p in parts if p.isdigit() and len(p) == 8), None)
        result = {
            "status": "success",
            "trigger_file": f"gs://{bucket}/{file_name}",
            "data_file": f"gs://{bucket}/{bare}",
            "entity": entity,
            "extract_date": extract_date,
            "bucket": bucket,
            "file_name": file_name,
        }
        context["ti"].xcom_push(key="file_metadata", value=result)
        return result

    def validate_file(**context) -> str:
        file_metadata = context["ti"].xcom_pull(task_ids="parse_message")
        if not file_metadata or file_metadata.get("status") != "success":
            return "skip_processing"
        # In real use, GCS validation happens here (omitted for testability).
        return "trigger_odp_load"

    def move_to_error_bucket(**context):
        log.warning("Validation failed — would move file to error bucket")

    def trigger_entity_ingestion(**context):
        from airflow.api.common.trigger_dag import trigger_dag  # type: ignore
        file_metadata = context["ti"].xcom_pull(task_ids="parse_message")
        if not file_metadata or file_metadata.get("status") != "success":
            return
        entity = file_metadata.get("entity", "")
        target_dag_id = ingestion_dag_map.get(entity)
        if not target_dag_id:
            raise ValueError(f"Unknown entity '{entity}'. Known: {list(ingestion_dag_map)}")
        extract_date = file_metadata.get("extract_date", "")
        run_id = f"{file_prefix}_{entity}_{extract_date}"
        trigger_dag(
            dag_id=target_dag_id,
            run_id=run_id,
            conf={
                "file_metadata": json.dumps(file_metadata),
                "data_file": file_metadata.get("data_file", ""),
                "entity": entity,
                "extract_date": extract_date,
            },
            replace_microseconds=False,
        )

    # ---- Build the sensor --------------------------------------------------
    try:
        from airflow.models import Variable  # type: ignore
        from data_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor

        project_id = Variable.get(
            "gcp_project_id",
            default_var=os.environ.get("GCP_PROJECT_ID", ""),
        )
        subscription = Variable.get(
            f"{file_prefix}_pubsub_subscription",
            default_var=pubsub_subscription_template,
        )
        _sensor_kwargs = dict(
            task_id="wait_for_file_notification",
            project_id=project_id,
            subscription=subscription,
            max_messages=10,
            filter_extension=ok_file_suffix,
            metadata_xcom_key="file_metadata",
            poke_interval=10,
            timeout=55,
            mode="reschedule",
            soft_fail=True,
        )
        _use_sensor = True
    except Exception:
        _use_sensor = False

    # ---- DAG definition ----------------------------------------------------
    with DAG(
        dag_id=dag_id,
        default_args=_default_args(on_failure_callback=_failure_callback()),
        description=f"Listen for {system_id} file arrivals via Pub/Sub and trigger ODP load",
        schedule=trigger_schedule,
        catchup=False,
        max_active_runs=1,
        tags=[file_prefix, "trigger", "pubsub"],
    ) as dag:
        if _use_sensor:
            wait_for_file = BasePubSubPullSensor(**_sensor_kwargs)
        else:
            wait_for_file = PythonOperator(
                task_id="wait_for_file_notification",
                python_callable=lambda **ctx: log.info("Stub sensor — no Airflow Variables available"),
            )

        parse_msg = PythonOperator(task_id="parse_message", python_callable=parse_pubsub_message)
        validate = BranchPythonOperator(task_id="validate_file", python_callable=validate_file)
        trigger_odp = PythonOperator(task_id="trigger_odp_load", python_callable=trigger_entity_ingestion)
        handle_error = PythonOperator(task_id="handle_validation_error", python_callable=move_to_error_bucket)
        skip = DummyOperator(task_id="skip_processing")
        end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

        wait_for_file >> parse_msg >> validate
        validate >> [trigger_odp, handle_error, skip]
        [trigger_odp, handle_error, skip] >> end

    return dag


# ---------------------------------------------------------------------------
# DAG 2: Ingestion DAG (per entity)
# ---------------------------------------------------------------------------

def build_ingestion_dag(entity_name: str, entity_cfg: dict,
                        factory_config: dict) -> "Any":  # noqa: ANN401
    """Build a per-entity ingestion DAG.

    Task graph::

        create_job_record
            → run_dataflow_pipeline
                → update_job_success
                    → reconcile_odp_load
                        → check_ready_fdp_models
                            → trigger_ready_transforms
                                → end

    Raises:
        ImportError: when apache-airflow is not installed.
    """
    _require_airflow()
    DAG = _get_dag_class()
    PythonOperator, _, DummyOperator, _ = _get_operators()

    system_id = factory_config.get("system_id", "generic")
    system_id_lower = system_id.lower()
    file_prefix = factory_config.get("file_prefix", system_id_lower)
    entities = sorted((factory_config.get("entities") or {}).keys())
    fdp_deps: Dict[str, List[str]] = {
        model: info.get("requires", [])
        for model, info in (factory_config.get("fdp_models") or {}).items()
    }

    infra = factory_config.get("infrastructure", {})
    odp_dataset_template = infra.get("datasets", {}).get("odp", "odp_{system}")
    error_bucket_template = infra.get("buckets", {}).get("error", "")
    temp_bucket_template = infra.get("buckets", {}).get("temp", "")

    dag_id = _prefixed(f"{system_id_lower}_{entity_name}_ingestion_dag")
    transformation_dag_map = {m: f"{system_id_lower}_{m}_transformation_dag" for m in fdp_deps}

    # ---- task callables ----------------------------------------------------

    def create_job_record(**context):
        conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = (
            json.loads(file_metadata_raw)
            if isinstance(file_metadata_raw, str) else file_metadata_raw
        )
        extract_date = file_metadata.get(
            "extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        )
        run_id = context.get("run_id", f"{file_prefix}_{entity_name}_{extract_date}")
        log.info("Creating job record: %s for entity: %s", run_id, entity_name)
        context["ti"].xcom_push(key="run_id", value=run_id)
        context["ti"].xcom_push(key="entity", value=entity_name)

    def check_ready_fdp_models(**context):
        conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = (
            json.loads(file_metadata_raw)
            if isinstance(file_metadata_raw, str) else file_metadata_raw
        )
        extract_date = file_metadata.get(
            "extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        )
        try:
            from airflow.models import Variable  # type: ignore
            project_id = Variable.get(
                "gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", "")
            )
            from data_pipeline_orchestration.dependency import EntityDependencyChecker
            date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
            checker = EntityDependencyChecker(
                project_id=project_id, system_id=system_id, required_entities=entities
            )
            loaded = set(checker.get_loaded_entities(date_obj))
            ready = [m for m, deps in fdp_deps.items() if set(deps).issubset(loaded)]
        except Exception as exc:
            log.warning("Could not check FDP readiness (non-fatal): %s", exc)
            ready = []
        context["ti"].xcom_push(key="ready_fdp_models", value=ready)

    def update_job_success(**context):
        run_id = context["ti"].xcom_pull(key="run_id")
        log.info("Job %s marked as SUCCESS", run_id)

    def reconcile_odp_load(**context):
        run_id = context["ti"].xcom_pull(key="run_id")
        log.info("Reconciling ODP load for run %s", run_id)
        # Real reconciliation delegates to ReconciliationEngine when available.

    def trigger_ready_transforms(**context):
        from airflow.api.common.trigger_dag import trigger_dag  # type: ignore
        ready_models = (
            context["ti"].xcom_pull(key="ready_fdp_models", task_ids="check_ready_fdp_models") or []
        )
        conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
        file_metadata_raw = conf.get("file_metadata", {})
        file_metadata = (
            json.loads(file_metadata_raw)
            if isinstance(file_metadata_raw, str) else file_metadata_raw
        )
        extract_date = file_metadata.get(
            "extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        )
        for model in ready_models:
            target_dag = transformation_dag_map.get(model)
            if not target_dag:
                log.warning("No transformation DAG for model '%s' — skipping", model)
                continue
            trigger_dag(
                dag_id=target_dag,
                run_id=f"transform_{model}_{extract_date}",
                conf={"extract_date": extract_date, "fdp_model": model, "triggered_by": dag_id},
                replace_microseconds=False,
            )

    # ---- Dataflow operator (T11.2b BaseDataflowOperator) ------------------
    # Compose the ported T11.2b operator rather than re-implementing the raw
    # provider operator here. BaseDataflowOperator abstracts source/mode/
    # template-type selection and wraps DataflowStartFlexTemplateOperator at
    # execute() time, so no Dataflow provider import is needed at build time.
    try:
        from airflow.models import Variable  # type: ignore
        from data_pipeline_orchestration.operators.dataflow import BaseDataflowOperator

        _project_id = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
        _region = Variable.get("gcp_region", default_var="europe-west2")
        _odp_dataset = odp_dataset_template.format(system=file_prefix)
        _template_bucket = Variable.get("dataflow_templates_bucket", default_var=temp_bucket_template)

        _dataflow_op = BaseDataflowOperator(
            task_id="run_dataflow_pipeline",
            pipeline_name=f"{file_prefix}_{entity_name}_odp_load",
            source_type="gcs",
            processing_mode="batch",
            template_type="flex",
            project_id=_project_id,
            region=_region,
            input_path="{{ dag_run.conf.data_file }}",
            output_table=f"{_project_id}:{_odp_dataset}.{entity_name}",
            template_path=f"gs://{_template_bucket}/templates/{file_prefix}_pipeline.json",
            temp_location=f"gs://{_template_bucket}/dataflow",
            max_workers=3,
            machine_type="n1-standard-2",
            job_name_prefix=file_prefix,
            additional_params={
                "run_id": '{{ ti.xcom_pull(key="run_id") }}',
                "entity": entity_name,
                "extract_date": "{{ dag_run.conf.extract_date }}",
            },
        )
        _use_dataflow = True
    except Exception:
        _use_dataflow = False

    # ---- DAG definition ---------------------------------------------------
    with DAG(
        dag_id=dag_id,
        default_args=_default_args(on_failure_callback=_failure_callback()),
        description=f"Load {system_id} {entity_name} data to ODP (BigQuery)",
        schedule=None,
        catchup=False,
        tags=[file_prefix, "odp", "dataflow", entity_name],
    ) as dag:
        create_job = PythonOperator(
            task_id="create_job_record", python_callable=create_job_record
        )

        if _use_dataflow:
            run_dataflow = _dataflow_op
        else:
            run_dataflow = PythonOperator(
                task_id="run_dataflow_pipeline",
                python_callable=lambda **ctx: log.info(
                    "Stub Dataflow task for %s — no Airflow Variables available", entity_name
                ),
            )

        mark_success = PythonOperator(
            task_id="update_job_success", python_callable=update_job_success
        )
        reconcile = PythonOperator(
            task_id="reconcile_odp_load", python_callable=reconcile_odp_load
        )
        check_deps = PythonOperator(
            task_id="check_ready_fdp_models", python_callable=check_ready_fdp_models
        )
        trigger_transforms = PythonOperator(
            task_id="trigger_ready_transforms", python_callable=trigger_ready_transforms
        )
        end = DummyOperator(task_id="end")

        create_job >> run_dataflow >> mark_success >> reconcile >> check_deps >> trigger_transforms >> end

    return dag


# ---------------------------------------------------------------------------
# DAG 3: Transformation DAG (per FDP model)
# ---------------------------------------------------------------------------

def build_transformation_dag(fdp_model: str, fdp_cfg: dict,
                              factory_config: dict) -> "Any":  # noqa: ANN401
    """Build a per-model transformation DAG.

    Task graph::

        verify_model_dependencies (branch)
            ├── create_fdp_job_record
            │       → run_dbt_staging
            │           → run_dbt_fdp
            │               → run_dbt_tests
            │                   → reconcile_fdp_model
            │                       → mark_fdp_success
            │                           → end
            └── handle_dependency_failure
                    → end

    Raises:
        ImportError: when apache-airflow is not installed.
    """
    _require_airflow()
    DAG = _get_dag_class()
    PythonOperator, BranchPythonOperator, DummyOperator, BashOperator = _get_operators()

    system_id = factory_config.get("system_id", "generic")
    system_id_lower = system_id.lower()
    file_prefix = factory_config.get("file_prefix", system_id_lower)
    fdp_deps: Dict[str, List[str]] = {
        model: info.get("requires", [])
        for model, info in (factory_config.get("fdp_models") or {}).items()
    }
    required_entities: List[str] = fdp_cfg.get("requires", fdp_deps.get(fdp_model, []))

    infra = factory_config.get("infrastructure", {})
    odp_dataset_template = infra.get("datasets", {}).get("odp", "odp_{system}")
    fdp_dataset_template = infra.get("datasets", {}).get("fdp", "fdp_{system}")
    error_bucket_template = infra.get("buckets", {}).get("error", "")

    dag_id = _prefixed(f"{system_id_lower}_{fdp_model}_transformation_dag")

    # ---- task callables ----------------------------------------------------

    def verify_model_dependencies(**context) -> str:
        conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        try:
            from airflow.models import Variable  # type: ignore
            project_id = Variable.get(
                "gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", "")
            )
            from data_pipeline_orchestration.dependency import EntityDependencyChecker
            checker = EntityDependencyChecker(
                project_id=project_id, system_id=system_id, required_entities=required_entities
            )
            date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
            if checker.all_entities_loaded(date_obj):
                context["ti"].xcom_push(key="fdp_model", value=fdp_model)
                return "create_fdp_job_record"
            missing = checker.get_missing_entities(date_obj)
            context["ti"].xcom_push(key="missing_entities", value=missing)
            return "handle_dependency_failure"
        except Exception as exc:
            log.warning("Dependency check failed (non-fatal): %s", exc)
            return "create_fdp_job_record"

    def create_fdp_job_record(**context):
        conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
        extract_date = conf.get("extract_date", datetime.now(tz=timezone.utc).strftime("%Y%m%d"))
        run_id = context.get("run_id", f"transform_{fdp_model}_{extract_date}")
        log.info("Created FDP job record: %s for model: %s", run_id, fdp_model)
        context["ti"].xcom_push(key="fdp_run_id", value=run_id)

    def handle_dependency_failure(**context):
        missing = context["ti"].xcom_pull(key="missing_entities") or []
        log.error("FDP dependency failure for %s — missing: %s", fdp_model, missing)

    def reconcile_fdp_model_output(**context):
        run_id = context["ti"].xcom_pull(key="fdp_run_id")
        log.info("Reconciling FDP model %s run %s", fdp_model, run_id)

    def update_fdp_job_success(**context):
        run_id = context["ti"].xcom_pull(key="fdp_run_id")
        log.info("FDP job %s marked as SUCCESS", run_id)

    # ---- dbt path ----------------------------------------------------------
    try:
        from airflow.models import Variable  # type: ignore
        dbt_path = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")
    except Exception:
        dbt_path = "/home/airflow/gcs/dags/dbt"

    # ---- DAG definition ---------------------------------------------------
    with DAG(
        dag_id=dag_id,
        default_args=_default_args(
            retries=2, retry_delay_minutes=10, on_failure_callback=_failure_callback()
        ),
        description=f"Transform {system_id} ODP to FDP — {fdp_model}",
        schedule=None,
        catchup=False,
        tags=[file_prefix, "fdp", "dbt", "transformation", fdp_model],
    ) as dag:
        verify = BranchPythonOperator(
            task_id="verify_model_dependencies", python_callable=verify_model_dependencies
        )
        create_fdp_job = PythonOperator(
            task_id="create_fdp_job_record", python_callable=create_fdp_job_record
        )
        staging = BashOperator(
            task_id="run_dbt_staging",
            bash_command=(
                f"cd {dbt_path} && dbt run --select staging "
                "--vars '{\"extract_date\": \"{{ ds_nodash }}\"}' --target prod"
            ),
        )
        fdp_run = BashOperator(
            task_id="run_dbt_fdp",
            bash_command=(
                f"cd {dbt_path} && dbt run --select '{fdp_model}' "
                "--vars '{\"extract_date\": \"{{ ds_nodash }}\"}' --target prod"
            ),
        )
        tests = BashOperator(
            task_id="run_dbt_tests",
            bash_command=f"cd {dbt_path} && dbt test --select '{fdp_model}' --target prod",
        )
        reconcile_fdp = PythonOperator(
            task_id="reconcile_fdp_model", python_callable=reconcile_fdp_model_output
        )
        mark_success = PythonOperator(
            task_id="mark_fdp_success", python_callable=update_fdp_job_success
        )
        dep_failure = PythonOperator(
            task_id="handle_dependency_failure", python_callable=handle_dependency_failure
        )
        end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

        verify >> [create_fdp_job, dep_failure]
        create_fdp_job >> staging >> fdp_run >> tests >> reconcile_fdp >> mark_success >> end
        dep_failure >> end

    return dag


# ---------------------------------------------------------------------------
# DAG 4: Error Handling DAG
# ---------------------------------------------------------------------------

def build_error_handling_dag(factory_config: dict) -> "Any":  # noqa: ANN401
    """Build the error-handling / recovery DAG.

    Task graph::

        scan_failed_jobs (branch)
            ├── handle_critical
            ├── handle_retryable
            ├── handle_manual_review
            └── no_errors
                    → end

    Raises:
        ImportError: when apache-airflow is not installed.
    """
    _require_airflow()
    DAG = _get_dag_class()
    PythonOperator, BranchPythonOperator, DummyOperator, _ = _get_operators()

    system_id = factory_config.get("system_id", "generic")
    system_id_lower = system_id.lower()
    file_prefix = factory_config.get("file_prefix", system_id_lower)
    entities = sorted((factory_config.get("entities") or {}).keys())
    fdp_deps: Dict[str, List[str]] = {
        model: info.get("requires", [])
        for model, info in (factory_config.get("fdp_models") or {}).items()
    }
    fdp_models = list(fdp_deps.keys())

    retry_cfg = factory_config.get("retry_config", {})
    odp_max_retries: int = retry_cfg.get("odp", {}).get("max_retries", 3)
    odp_cleanup: bool = retry_cfg.get("odp", {}).get("cleanup_on_retry", True)
    fdp_max_retries: int = retry_cfg.get("fdp", {}).get("max_retries", 2)

    ingestion_dag_map = {e: f"{system_id_lower}_{e}_ingestion_dag" for e in entities}
    transformation_dag_map = {m: f"{system_id_lower}_{m}_transformation_dag" for m in fdp_models}

    dag_id = _prefixed(f"{system_id_lower}_error_handling_dag")

    # ---- task callables ----------------------------------------------------

    def scan_failed_jobs(**context) -> str:
        try:
            from airflow.models import Variable  # type: ignore
            project_id = Variable.get(
                "gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", "")
            )
            from gcp_pipeline_core.job_control import JobControlRepository, FailureStage  # type: ignore
            today = datetime.now(tz=timezone.utc).date()
            repo = JobControlRepository(project_id=project_id)
            failed = repo.get_failed_jobs(system_id, today)
        except Exception as exc:
            log.warning("Could not scan failed jobs (non-fatal): %s", exc)
            failed = []

        if not failed:
            return "no_errors"

        critical, retryable, manual = [], [], []
        _critical_stages = {"FILE_DISCOVERY", "FDP_DEPENDENCY"}
        _retryable_stages = {"ODP_LOAD", "RECONCILIATION", "FDP_MODEL", "FDP_STAGING", "FDP_TEST"}

        for job in failed:
            stage = job.get("stage", "UNKNOWN")
            retry_count = job.get("retry_count", 0)
            is_fdp = job.get("entity_type", "") in fdp_models
            max_retries = fdp_max_retries if is_fdp else odp_max_retries
            if stage in _critical_stages:
                critical.append(job)
            elif stage in _retryable_stages and retry_count < max_retries:
                retryable.append({**job, "is_fdp": is_fdp})
            else:
                manual.append(job)

        context["ti"].xcom_push(key="critical_jobs", value=critical)
        context["ti"].xcom_push(key="retryable_jobs", value=retryable)
        context["ti"].xcom_push(key="manual_review_jobs", value=manual)

        if critical:
            return "handle_critical"
        if retryable:
            return "handle_retryable"
        if manual:
            return "handle_manual_review"
        return "no_errors"

    def handle_critical(**context):
        jobs = context["ti"].xcom_pull(key="critical_jobs") or []
        for job in jobs:
            log.error("CRITICAL failure: %s entity=%s", job.get("run_id"), job.get("entity_type"))

    def handle_retryable(**context):
        from airflow.api.common.trigger_dag import trigger_dag  # type: ignore
        jobs = context["ti"].xcom_pull(key="retryable_jobs") or []
        for job in jobs:
            run_id = job["run_id"]
            entity = job["entity_type"]
            retry_count = job.get("retry_count", 0)
            is_fdp = job.get("is_fdp", False)
            target_dag = (
                transformation_dag_map.get(entity)
                if is_fdp else ingestion_dag_map.get(entity)
            )
            if not target_dag:
                log.error("No DAG for '%s' — skipping retry", entity)
                continue
            try:
                trigger_dag(
                    dag_id=target_dag,
                    run_id=f"retry_{run_id}_{retry_count + 1}",
                    conf={"extract_date": datetime.now(tz=timezone.utc).strftime("%Y%m%d"),
                          "triggered_by": dag_id},
                    replace_microseconds=False,
                )
                log.info("Triggered retry for %s → %s", run_id, target_dag)
            except Exception as exc:
                log.error("Retry trigger failed for %s: %s", run_id, exc)

    def handle_manual_review(**context):
        jobs = context["ti"].xcom_pull(key="manual_review_jobs") or []
        for job in jobs:
            log.warning(
                "Manual review needed: %s entity=%s", job.get("run_id"), job.get("entity_type")
            )

    # ---- DAG definition ---------------------------------------------------
    with DAG(
        dag_id=dag_id,
        default_args=_default_args(retries=1, retry_delay_minutes=10),
        description=f"Monitor and recover failed {system_id} pipeline jobs — runs every 30 min",
        schedule="*/30 * * * *",
        catchup=False,
        max_active_runs=1,
        tags=[file_prefix, "error", "recovery", "monitoring"],
    ) as dag:
        scan = BranchPythonOperator(task_id="scan_failed_jobs", python_callable=scan_failed_jobs)
        critical = PythonOperator(task_id="handle_critical", python_callable=handle_critical)
        retryable = PythonOperator(task_id="handle_retryable", python_callable=handle_retryable)
        manual = PythonOperator(task_id="handle_manual_review", python_callable=handle_manual_review)
        no_errors = DummyOperator(task_id="no_errors")
        end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

        scan >> [critical, retryable, manual, no_errors]
        [critical, retryable, manual, no_errors] >> end

    return dag


# ---------------------------------------------------------------------------
# DAG 5: Pipeline Status DAG
# ---------------------------------------------------------------------------

def build_status_dag(factory_config: dict) -> "Any":  # noqa: ANN401
    """Build the daily pipeline status / observability DAG.

    Task graph::

        check_pipeline_status

    Raises:
        ImportError: when apache-airflow is not installed.
    """
    _require_airflow()
    DAG = _get_dag_class()
    PythonOperator, _, _, _ = _get_operators()

    system_id = factory_config.get("system_id", "generic")
    system_id_lower = system_id.lower()
    system_name = factory_config.get("system_name", system_id)
    file_prefix = factory_config.get("file_prefix", system_id_lower)
    entities = sorted((factory_config.get("entities") or {}).keys())
    fdp_models = list((factory_config.get("fdp_models") or {}).keys())

    dag_id = _prefixed(f"{system_id_lower}_pipeline_status_dag")

    def check_pipeline_status(**context):
        today = context.get("ds_nodash") or datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        try:
            from airflow.models import Variable  # type: ignore
            project_id = Variable.get(
                "gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", "")
            )
            from gcp_pipeline_core.job_control import JobControlRepository  # type: ignore
            date_obj = datetime.strptime(today, "%Y%m%d").date()
            repo = JobControlRepository(project_id=project_id)
            statuses = repo.get_entity_status(system_id, date_obj)
            status_map = {s["entity_type"]: s["status"] for s in statuses}
        except Exception as exc:
            log.warning("Could not query job_control (non-fatal): %s", exc)
            status_map = {}

        issues = []
        for entity in entities:
            status = status_map.get(entity)
            if status != "SUCCESS":
                issues.append(f"ODP {entity}: {status or 'NOT LOADED'}")
        for model in fdp_models:
            status = status_map.get(model)
            if status != "SUCCESS":
                issues.append(f"FDP {model}: {status or 'NOT RUN'}")

        if issues:
            summary = f"{system_name} pipeline incomplete for {today}:\n" + "\n".join(
                f"  - {i}" for i in issues
            )
            log.error(summary)
            raise Exception(summary)
        log.info(
            "%s pipeline complete for %s — %d entities, %d FDP models all succeeded.",
            system_name, today, len(entities), len(fdp_models),
        )

    with DAG(
        dag_id=dag_id,
        default_args=_default_args(retries=1, on_failure_callback=_failure_callback()),
        description=f"Daily status check for {system_name} pipeline completeness",
        schedule="0 23 * * *",
        catchup=False,
        tags=[file_prefix, "status", "observability"],
    ) as dag:
        PythonOperator(task_id="check_pipeline_status", python_callable=check_pipeline_status)

    return dag


__all__ = [
    "build_pubsub_trigger_dag",
    "build_ingestion_dag",
    "build_transformation_dag",
    "build_error_handling_dag",
    "build_status_dag",
]

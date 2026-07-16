"""Structural tests for the ``create_dags`` entrypoint (T11.2c + T11.2d).

These verify the full DAG set ``create_dags`` wires — **four** DAG types:
pub/sub trigger + one ingestion DAG per entity (#86) plus one transformation
DAG per FDP model + a pipeline-status DAG (#87). The periodic
``error_handling`` DAG is a 5th builder reachable via ``DagFactory`` but is
deliberately NOT produced by ``create_dags``.

Tasks are constructed but never executed, so only the ``apache-airflow``
package itself is required (no scheduler, no live GCP). ``Variable.get`` is
patched so no Airflow metadata DB is needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

pytest.importorskip("airflow", reason="apache-airflow required for create_dags tests")

from airflow import DAG  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    """A minimal but representative system.yaml config dict (2 entities)."""
    return {
        "system_id": "GENERIC",
        "system_name": "Generic",
        "file_prefix": "generic",
        "ok_file_suffix": ".ok",
        "trigger_schedule": "*/5 * * * *",
        "environment": "int",
        "entities": {
            "customers": {"description": "Customer records"},
            "accounts": {"description": "Account records"},
        },
        "fdp_models": {
            "customer_account": {
                "requires": ["customers", "accounts"],
                "description": "Joined customer-account FDP",
            }
        },
        "infrastructure": {
            "pubsub": {
                "subscription": "projects/{project_id}/subscriptions/generic-landing-sub",
            },
            "datasets": {"odp": "odp_{system}", "fdp": "fdp_{system}"},
            "buckets": {
                "error": "{project_id}-generic-error",
                "temp": "{project_id}-generic-temp",
            },
        },
    }


@pytest.fixture
def patched_variable():
    """Return defaults from Variable.get so no Airflow DB is needed."""
    with patch(
        "airflow.models.Variable.get",
        side_effect=lambda k, **kw: kw.get("default_var", ""),
    ):
        yield


def _task_ids(dag: DAG) -> set:
    return {t.task_id for t in dag.tasks}


# ---------------------------------------------------------------------------
# create_dags importability + registration
# ---------------------------------------------------------------------------

def test_create_dags_module_imports_cleanly():
    """The entrypoint module must import without eager top-level
    job-control or Airflow-3.x-only operator imports — construction is
    delegated to _dag_builders, which lazy-imports Airflow inside the body."""
    from data_pipeline_orchestration.factories import dag_factory

    assert hasattr(dag_factory, "create_dags")
    assert callable(dag_factory.create_dags)


def test_registers_full_dag_set(sample_config, patched_variable):
    """T11.2d: 1 trigger + 2 ingestion + 1 transformation + 1 status = 5 DAGs."""
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    ns: dict = {}
    create_dags(sample_config, ns)

    # 2 entities + 1 fdp model → 1 trigger + 2 ingestion + 1 transform + 1 status
    assert len(ns) == 5
    assert "generic_pubsub_trigger_dag" in ns
    assert "generic_customers_ingestion_dag" in ns
    assert "generic_accounts_ingestion_dag" in ns
    assert "generic_customer_account_transformation_dag" in ns
    assert "generic_pipeline_status_dag" in ns
    for dag in ns.values():
        assert isinstance(dag, DAG)
        # injected under its own dag_id so the DagBag discovers it
    for dag_id, dag in ns.items():
        assert dag.dag_id == dag_id


def test_all_four_dag_types_produced(sample_config, patched_variable):
    """DoD #3: create_dags produces all 4 DAG types — assert the full set.

    Asserts by dag_id *type* substring, not just count, so the acceptance gate
    genuinely covers each of the four categories.
    """
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    ns: dict = {}
    create_dags(sample_config, ns)
    joined = " ".join(ns.keys())

    assert "pubsub_trigger" in joined        # type 1: ingestion-side (#86)
    assert "ingestion" in joined             # type 2: ingestion-side (#86)
    assert "transformation" in joined        # type 3: #87
    assert "pipeline_status" in joined       # type 4: #87

    # error_handling is a 5th builder, NOT wired into create_dags
    assert "error_handling" not in joined


def test_every_dag_routes_failures_to_dlq_quarantine(sample_config, patched_variable):
    """DoD #2: the failure callback (DLQ/quarantine router) is wired as the
    on_failure_callback on every DAG create_dags builds."""
    from data_pipeline_orchestration.factories.dag_factory import create_dags
    from data_pipeline_orchestration.callbacks import on_failure_callback

    ns: dict = {}
    create_dags(sample_config, ns)

    for dag_id, dag in ns.items():
        assert dag.default_args.get("on_failure_callback") is on_failure_callback, (
            f"{dag_id} is missing the on_failure_callback DLQ/quarantine router"
        )


# ---------------------------------------------------------------------------
# Pub/Sub trigger DAG structure
# ---------------------------------------------------------------------------

def test_trigger_dag_task_set_and_edges(sample_config, patched_variable):
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    ns: dict = {}
    create_dags(sample_config, ns)
    trigger = ns["generic_pubsub_trigger_dag"]

    task_ids = _task_ids(trigger)
    assert {
        "wait_for_file_notification",
        "parse_message",
        "validate_file",
        "trigger_odp_load",
        "handle_validation_error",
        "skip_processing",
        "end",
    } <= task_ids

    # schedule comes from trigger_schedule
    assert trigger.schedule_interval == "*/5 * * * *"

    # parse_message → validate_file → 3 branches → end
    validate = trigger.get_task("validate_file")
    branch_ids = {t.task_id for t in validate.downstream_list}
    assert {"trigger_odp_load", "handle_validation_error", "skip_processing"} <= branch_ids

    end = trigger.get_task("end")
    end_upstream = {t.task_id for t in end.upstream_list}
    assert {"trigger_odp_load", "handle_validation_error", "skip_processing"} <= end_upstream


def test_trigger_dag_composes_t112b_pubsub_sensor(sample_config, patched_variable):
    """DoD #3: the trigger DAG must use the ported T11.2b BasePubSubPullSensor,
    not the PythonOperator stub fallback."""
    from data_pipeline_orchestration.factories.dag_factory import create_dags
    from data_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor

    ns: dict = {}
    create_dags(sample_config, ns)
    trigger = ns["generic_pubsub_trigger_dag"]

    wait_task = trigger.get_task("wait_for_file_notification")
    assert isinstance(wait_task, BasePubSubPullSensor)


# ---------------------------------------------------------------------------
# Ingestion DAG structure + T11.2b operator composition
# ---------------------------------------------------------------------------

def test_ingestion_dag_task_set_and_linear_chain(sample_config, patched_variable):
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    ns: dict = {}
    create_dags(sample_config, ns)
    ingestion = ns["generic_customers_ingestion_dag"]

    task_ids = _task_ids(ingestion)
    assert {
        "create_job_record",
        "run_dataflow_pipeline",
        "update_job_success",
        "reconcile_odp_load",
        "check_ready_fdp_models",
        "trigger_ready_transforms",
        "end",
    } <= task_ids

    # Triggered externally → no schedule
    assert ingestion.schedule_interval is None

    # Linear chain: end is a descendant of create_job_record
    create_job = ingestion.get_task("create_job_record")
    downstream = create_job.get_flat_relatives(upstream=False)
    assert ingestion.get_task("end") in downstream


def test_ingestion_dag_composes_t112b_dataflow_operator(sample_config, patched_variable):
    """DoD #3: the ingestion DAG must use the ported T11.2b BaseDataflowOperator,
    not a re-implemented / raw provider operator."""
    from data_pipeline_orchestration.factories.dag_factory import create_dags
    from data_pipeline_orchestration.operators.dataflow import BaseDataflowOperator

    ns: dict = {}
    create_dags(sample_config, ns)
    ingestion = ns["generic_accounts_ingestion_dag"]

    dataflow_task = ingestion.get_task("run_dataflow_pipeline")
    assert isinstance(dataflow_task, BaseDataflowOperator)
    # output table is wired per entity
    assert dataflow_task.output_table.endswith(".accounts")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

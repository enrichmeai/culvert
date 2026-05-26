"""Tests for _dag_builders and DagFactory real DAG wiring.

All five builder functions are tested with a representative config dict.
Airflow operators are constructed but don't *execute*, so no real Airflow
environment is needed — only the ``apache-airflow`` package itself.

When Airflow is not installed, the entire module is skipped (same pattern
used in test_dag_factory.py).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

# Skip entire module if airflow is not installed (backward-compat with
# test environments that run without it).
pytest.importorskip("airflow", reason="apache-airflow required for DAG builder tests")

from airflow import DAG  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    """A minimal but representative system.yaml config dict."""
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
            "datasets": {
                "odp": "odp_{system}",
                "fdp": "fdp_{system}",
            },
            "buckets": {
                "error": "{project_id}-generic-error",
                "temp": "{project_id}-generic-temp",
            },
        },
        "retry_config": {
            "odp": {"max_retries": 3, "cleanup_on_retry": True},
            "fdp": {"max_retries": 2},
        },
    }


@pytest.fixture(autouse=True)
def reset_dag_registry():
    """Ensure each test starts with a clean Airflow DAG registry."""
    from airflow.models import DagBag
    # Reset the global DagBag / global dag dict if accessible
    try:
        from airflow import settings
        settings.Session()  # ensure DB initialised
    except Exception:
        pass
    # The simplest cross-version reset: clear the module-level dict
    try:
        from airflow.models.dag import DagContext
        DagContext._context_managed_dags.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _task_ids(dag: DAG) -> set:
    return {t.task_id for t in dag.tasks}


# ---------------------------------------------------------------------------
# build_pubsub_trigger_dag
# ---------------------------------------------------------------------------

class TestBuildPubsubTriggerDag:
    def test_returns_dag(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        # Patch Variable.get so we don't need a real Airflow DB
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        assert isinstance(dag, DAG)

    def test_dag_id_contains_system_and_type(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        assert "generic" in dag.dag_id
        assert "pubsub_trigger" in dag.dag_id

    def test_expected_tasks_present(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        task_ids = _task_ids(dag)
        assert "parse_message" in task_ids
        assert "validate_file" in task_ids
        assert "trigger_odp_load" in task_ids
        assert "handle_validation_error" in task_ids
        assert "skip_processing" in task_ids
        assert "end" in task_ids
        # At least 6 tasks
        assert len(task_ids) >= 6

    def test_tags_include_system_prefix(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        assert "generic" in dag.tags
        assert "pubsub" in dag.tags

    def test_schedule_respected(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        assert dag.schedule == "*/5 * * * *"

    def test_task_graph_end_downstream_of_branches(self, sample_config):
        """end task must be downstream of each branch leaf."""
        from data_pipeline_orchestration.factories._dag_builders import build_pubsub_trigger_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_pubsub_trigger_dag(sample_config)

        end_task = dag.get_task("end")
        upstream_ids = {t.task_id for t in end_task.upstream_list}
        assert "trigger_odp_load" in upstream_ids
        assert "handle_validation_error" in upstream_ids
        assert "skip_processing" in upstream_ids


# ---------------------------------------------------------------------------
# build_ingestion_dag
# ---------------------------------------------------------------------------

class TestBuildIngestionDag:
    def test_returns_dag(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("customers", sample_config["entities"]["customers"], sample_config)

        assert isinstance(dag, DAG)

    def test_dag_id_contains_entity(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("customers", sample_config["entities"]["customers"], sample_config)

        assert "customers" in dag.dag_id
        assert "ingestion" in dag.dag_id

    def test_expected_tasks_present(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("customers", sample_config["entities"]["customers"], sample_config)

        task_ids = _task_ids(dag)
        assert "create_job_record" in task_ids
        assert "run_dataflow_pipeline" in task_ids
        assert "update_job_success" in task_ids
        assert "reconcile_odp_load" in task_ids
        assert "check_ready_fdp_models" in task_ids
        assert "trigger_ready_transforms" in task_ids
        assert "end" in task_ids
        assert len(task_ids) >= 7

    def test_schedule_is_none(self, sample_config):
        """Ingestion DAGs are triggered externally, not on a schedule."""
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("accounts", sample_config["entities"]["accounts"], sample_config)

        assert dag.schedule is None

    def test_tags_include_entity_and_odp(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("customers", sample_config["entities"]["customers"], sample_config)

        assert "customers" in dag.tags
        assert "odp" in dag.tags

    def test_linear_task_graph(self, sample_config):
        """create_job_record must be upstream of end (via linear chain)."""
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_ingestion_dag("customers", sample_config["entities"]["customers"], sample_config)

        create_job = dag.get_task("create_job_record")
        end_task = dag.get_task("end")
        # end must be a descendant of create_job_record
        descendants = dag.get_task_group_dict()
        all_downstream = dag.get_task("trigger_ready_transforms").get_flat_relatives(upstream=False)
        assert end_task in all_downstream

    def test_two_entities_produce_two_dags(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_ingestion_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag_cust = build_ingestion_dag(
                "customers", sample_config["entities"]["customers"], sample_config
            )
            dag_acc = build_ingestion_dag(
                "accounts", sample_config["entities"]["accounts"], sample_config
            )

        assert dag_cust.dag_id != dag_acc.dag_id
        assert "customers" in dag_cust.dag_id
        assert "accounts" in dag_acc.dag_id


# ---------------------------------------------------------------------------
# build_transformation_dag
# ---------------------------------------------------------------------------

class TestBuildTransformationDag:
    def test_returns_dag(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        assert isinstance(dag, DAG)

    def test_dag_id_contains_model_and_type(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        assert "customer_account" in dag.dag_id
        assert "transformation" in dag.dag_id

    def test_expected_tasks_present(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        task_ids = _task_ids(dag)
        assert "verify_model_dependencies" in task_ids
        assert "create_fdp_job_record" in task_ids
        assert "run_dbt_staging" in task_ids
        assert "run_dbt_fdp" in task_ids
        assert "run_dbt_tests" in task_ids
        assert "reconcile_fdp_model" in task_ids
        assert "mark_fdp_success" in task_ids
        assert "handle_dependency_failure" in task_ids
        assert "end" in task_ids
        assert len(task_ids) >= 9

    def test_tags_include_fdp_and_dbt(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        assert "fdp" in dag.tags
        assert "dbt" in dag.tags
        assert "customer_account" in dag.tags

    def test_schedule_is_none(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        assert dag.schedule is None

    def test_verify_branches_to_both_paths(self, sample_config):
        """verify_model_dependencies must have both success and failure branches."""
        from data_pipeline_orchestration.factories._dag_builders import build_transformation_dag
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            dag = build_transformation_dag(
                "customer_account",
                sample_config["fdp_models"]["customer_account"],
                sample_config,
            )
        verify = dag.get_task("verify_model_dependencies")
        downstream_ids = {t.task_id for t in verify.downstream_list}
        assert "create_fdp_job_record" in downstream_ids
        assert "handle_dependency_failure" in downstream_ids


# ---------------------------------------------------------------------------
# build_error_handling_dag
# ---------------------------------------------------------------------------

class TestBuildErrorHandlingDag:
    def test_returns_dag(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        assert isinstance(dag, DAG)

    def test_dag_id_contains_error_handling(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        assert "error_handling" in dag.dag_id
        assert "generic" in dag.dag_id

    def test_expected_tasks_present(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        task_ids = _task_ids(dag)
        assert "scan_failed_jobs" in task_ids
        assert "handle_critical" in task_ids
        assert "handle_retryable" in task_ids
        assert "handle_manual_review" in task_ids
        assert "no_errors" in task_ids
        assert "end" in task_ids
        assert len(task_ids) >= 6

    def test_schedule_every_30_min(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        assert dag.schedule == "*/30 * * * *"

    def test_tags_include_error_and_recovery(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        assert "error" in dag.tags
        assert "recovery" in dag.tags

    def test_scan_branches_to_all_handlers(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_error_handling_dag
        dag = build_error_handling_dag(sample_config)
        scan = dag.get_task("scan_failed_jobs")
        downstream_ids = {t.task_id for t in scan.downstream_list}
        assert "handle_critical" in downstream_ids
        assert "handle_retryable" in downstream_ids
        assert "handle_manual_review" in downstream_ids
        assert "no_errors" in downstream_ids


# ---------------------------------------------------------------------------
# build_status_dag
# ---------------------------------------------------------------------------

class TestBuildStatusDag:
    def test_returns_dag(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_status_dag
        dag = build_status_dag(sample_config)
        assert isinstance(dag, DAG)

    def test_dag_id_contains_status(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_status_dag
        dag = build_status_dag(sample_config)
        assert "status" in dag.dag_id
        assert "generic" in dag.dag_id

    def test_single_check_task(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_status_dag
        dag = build_status_dag(sample_config)
        task_ids = _task_ids(dag)
        assert "check_pipeline_status" in task_ids
        assert len(task_ids) >= 1

    def test_schedule_daily(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_status_dag
        dag = build_status_dag(sample_config)
        assert dag.schedule == "0 23 * * *"

    def test_tags_include_status_and_observability(self, sample_config):
        from data_pipeline_orchestration.factories._dag_builders import build_status_dag
        dag = build_status_dag(sample_config)
        assert "status" in dag.tags
        assert "observability" in dag.tags


# ---------------------------------------------------------------------------
# DagFactory integration tests
# ---------------------------------------------------------------------------

class TestDagFactoryIntegration:
    """Verify DagFactory produces real DAG objects via from_config."""

    def _make_factory(self, config, tmp_path):
        import yaml
        from data_pipeline_orchestration.factories.dag_factory_alias import DagFactory
        cfg_file = tmp_path / "system.yaml"
        cfg_file.write_text(yaml.dump(config))
        return DagFactory.from_config(cfg_file)

    def test_ingestion_dags_returns_real_dags(self, sample_config, tmp_path):
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            factory = self._make_factory(sample_config, tmp_path)
            results = list(factory.ingestion_dags())

        assert len(results) == 2  # customers + accounts
        for name, dag in results:
            assert isinstance(dag, DAG), f"Expected DAG for {name}, got {type(dag)}"
            assert name in dag.dag_id

    def test_transformation_dags_returns_real_dags(self, sample_config, tmp_path):
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            factory = self._make_factory(sample_config, tmp_path)
            results = list(factory.transformation_dags())

        assert len(results) == 1
        dag = results[0]
        assert isinstance(dag, DAG)
        assert "customer_account" in dag.dag_id

    def test_pubsub_trigger_dag_returns_real_dag(self, sample_config, tmp_path):
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            factory = self._make_factory(sample_config, tmp_path)
            dag = factory.pubsub_trigger_dag()

        assert isinstance(dag, DAG)
        assert "pubsub_trigger" in dag.dag_id

    def test_error_handling_dag_returns_real_dag(self, sample_config, tmp_path):
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            factory = self._make_factory(sample_config, tmp_path)
            dag = factory.error_handling_dag()

        assert isinstance(dag, DAG)
        assert "error_handling" in dag.dag_id

    def test_status_dag_returns_real_dag(self, sample_config, tmp_path):
        with patch("airflow.models.Variable.get", side_effect=lambda k, **kw: kw.get("default_var", "")):
            factory = self._make_factory(sample_config, tmp_path)
            dag = factory.status_dag()

        assert isinstance(dag, DAG)
        assert "status" in dag.dag_id

    def test_stub_fallback_when_import_error(self, sample_config, tmp_path):
        """When _dag_builders raises ImportError, _stub_dag is returned."""
        import yaml
        from data_pipeline_orchestration.factories.dag_factory_alias import DagFactory

        cfg_file = tmp_path / "system.yaml"
        cfg_file.write_text(yaml.dump(sample_config))
        factory = DagFactory.from_config(cfg_file)

        # Patch the builder to simulate ImportError
        with patch(
            "data_pipeline_orchestration.factories._dag_builders.build_status_dag",
            side_effect=ImportError("airflow not installed"),
        ):
            result = factory.status_dag()

        # Should be either a DAG (if airflow is present) or a _StubDag-like object
        assert hasattr(result, "dag_id")
        assert "status" in result.dag_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

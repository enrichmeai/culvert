"""
Unit tests for the config-driven create_dags() pipeline factory.

Tests cover:
- DAG structure (IDs, task graph, tags)
- Callable logic for each pipeline stage
- Status DAG alert / pass behaviour
- Infrastructure template resolution
- FDP dependency parsing
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch, call

pytest.importorskip("airflow", reason="apache-airflow required")

from gcp_pipeline_orchestration.factories.dag_factory import (
    create_dags,
    _entity_names,
    _fdp_dependencies,
    _resolve_infra,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def system_config():
    return {
        "system_id": "GENERIC",
        "system_name": "Generic System",
        "file_prefix": "generic",
        "ok_file_suffix": ".ok",
        "entities": {
            "customers": {"description": "Customer records"},
            "accounts": {"description": "Account records"},
        },
        "fdp_models": {
            "event_transaction_excess": {
                "type": "map",
                "requires": ["customers", "accounts"],
            },
            "portfolio_account_excess": {
                "type": "map",
                "requires": ["accounts"],
            },
        },
        "infrastructure": {
            "buckets": {
                "landing": "{project_id}-{system}-{env}-landing",
                "archive": "{project_id}-{system}-{env}-archive",
                "error": "{project_id}-{system}-{env}-error",
                "temp": "{project_id}-{system}-{env}-temp",
            },
            "pubsub": {
                "topic": "{system}-file-notifications",
                "subscription": "{system}-file-notifications-sub",
            },
            "datasets": {
                "odp": "odp_{system}",
                "fdp": "fdp_{system}",
            },
        },
    }


@pytest.fixture
def mock_airflow_variable():
    """Patch airflow Variable.get to return test values."""
    from airflow.providers.standard.operators.empty import EmptyOperator

    # BaseDataflowOperator uses old Airflow 2 BaseOperator API.
    # Replace with a thin stub that accepts any kwargs and delegates only
    # task_id to EmptyOperator so Airflow 3 SDK registers it correctly.
    class _StubDataflowOperator(EmptyOperator):
        def __init__(self, **kwargs):
            super().__init__(task_id=kwargs["task_id"])

    with patch("gcp_pipeline_orchestration.factories.dag_factory.Variable") as mock_var, \
         patch("gcp_pipeline_orchestration.factories.dag_factory.BaseDataflowOperator", _StubDataflowOperator):
        mock_var.get.side_effect = lambda key, default_var=None: {
            "gcp_project_id": "test-project",
            "gcp_region": "europe-west2",
            "environment": "int",
            "dbt_project_path": "/dbt",
            "dataflow_templates_bucket": "test-project-generic-int-temp",
        }.get(key, default_var)
        yield mock_var


# =============================================================================
# Helpers
# =============================================================================

def _make_context(dag_run_conf=None, xcom_values=None, run_id="run-001", ds_nodash="20260317"):
    """Build a minimal Airflow task context dict."""
    ti = MagicMock()
    ti.xcom_pull.side_effect = lambda key=None, task_ids=None: (xcom_values or {}).get(key)
    dag_run = MagicMock()
    dag_run.conf = dag_run_conf or {}
    return {
        "ti": ti,
        "dag_run": dag_run,
        "run_id": run_id,
        "ds_nodash": ds_nodash,
        "task_instance": MagicMock(task_id="some_task"),
    }


# =============================================================================
# Helper function tests
# =============================================================================

class TestHelpers:
    def test_entity_names(self, system_config):
        assert _entity_names(system_config) == ["customers", "accounts"]

    def test_entity_names_empty(self):
        assert _entity_names({}) == []

    def test_fdp_dependencies(self, system_config):
        deps = _fdp_dependencies(system_config)
        assert deps["event_transaction_excess"] == ["customers", "accounts"]
        assert deps["portfolio_account_excess"] == ["accounts"]

    def test_fdp_dependencies_empty(self):
        assert _fdp_dependencies({}) == {}

    def test_resolve_infra(self, system_config):
        infra = _resolve_infra(system_config, "my-project", "int")
        assert infra["landing_bucket"] == "my-project-generic-int-landing"
        assert infra["error_bucket"] == "my-project-generic-int-error"
        assert infra["pubsub_subscription"] == "generic-file-notifications-sub"
        assert infra["temp_bucket"] == "my-project-generic-int-temp"

    def test_resolve_infra_missing_keys(self):
        config = {"file_prefix": "myapp", "infrastructure": {}}
        infra = _resolve_infra(config, "proj", "prod")
        assert infra["landing_bucket"] == ""
        assert infra["pubsub_subscription"] == ""


# =============================================================================
# create_dags — DAG structure
# =============================================================================

class TestCreateDags:
    def test_creates_four_dags(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        assert len(ns) == 4

    def test_dag_ids(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        assert "generic_pubsub_trigger_dag" in ns
        assert "generic_ingestion_dag" in ns
        assert "generic_transformation_dag" in ns
        assert "generic_pipeline_status_dag" in ns

    def test_system_id_lowercased_in_dag_ids(self, system_config, mock_airflow_variable):
        config = dict(system_config, system_id="UPPER_SYSTEM")
        ns = {}
        create_dags(config, ns)
        assert "upper_system_pubsub_trigger_dag" in ns

    def test_trigger_dag_tags(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        assert "generic" in dag.tags
        assert "trigger" in dag.tags
        assert "pubsub" in dag.tags

    def test_ingestion_dag_tags(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_ingestion_dag"]
        assert "odp" in dag.tags
        assert "dataflow" in dag.tags

    def test_transformation_dag_tags(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_transformation_dag"]
        assert "fdp" in dag.tags
        assert "dbt" in dag.tags

    def test_status_dag_tags(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pipeline_status_dag"]
        assert "status" in dag.tags
        assert "observability" in dag.tags

    def test_status_dag_has_daily_schedule(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pipeline_status_dag"]
        assert dag.schedule == "0 23 * * *"

    def test_pipeline_dags_have_no_schedule(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        for dag_id in ["generic_pubsub_trigger_dag", "generic_ingestion_dag", "generic_transformation_dag"]:
            assert ns[dag_id].schedule is None

    def test_trigger_dag_task_ids(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        task_ids = {t.task_id for t in ns["generic_pubsub_trigger_dag"].tasks}
        assert "wait_for_file_notification" in task_ids
        assert "parse_message" in task_ids
        assert "validate_file" in task_ids
        assert "trigger_odp_load" in task_ids
        assert "handle_validation_error" in task_ids
        assert "skip_processing" in task_ids
        assert "end" in task_ids

    def test_ingestion_dag_task_ids(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        task_ids = {t.task_id for t in ns["generic_ingestion_dag"].tasks}
        assert "create_job_record" in task_ids
        assert "run_dataflow_pipeline" in task_ids
        assert "update_job_success" in task_ids
        assert "reconcile_odp_load" in task_ids
        assert "check_ready_fdp_models" in task_ids
        assert "trigger_ready_transforms" in task_ids
        assert "end" in task_ids

    def test_transformation_dag_task_ids(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        task_ids = {t.task_id for t in ns["generic_transformation_dag"].tasks}
        assert "verify_model_dependencies" in task_ids
        assert "create_fdp_job_record" in task_ids
        assert "run_dbt_staging" in task_ids
        assert "run_dbt_fdp" in task_ids
        assert "run_dbt_tests" in task_ids
        assert "reconcile_fdp_model" in task_ids
        assert "mark_fdp_success" in task_ids
        assert "handle_dependency_failure" in task_ids
        assert "end" in task_ids

    def test_status_dag_task_ids(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        task_ids = {t.task_id for t in ns["generic_pipeline_status_dag"].tasks}
        assert "check_pipeline_status" in task_ids


# =============================================================================
# Trigger DAG callable logic
# =============================================================================

class TestPubSubTriggerCallables:
    def _get_callables(self, system_config, mock_airflow_variable):
        """Extract callable functions from the trigger DAG tasks."""
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        tasks = {t.task_id: t for t in dag.tasks}
        return tasks

    def test_parse_message_valid_ok_file(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        parse_task = next(t for t in dag.tasks if t.task_id == "parse_message")
        message = {"name": "generic/customers/generic_customers_20260317.ok", "bucket": "test-bucket"}
        import json
        context = _make_context()
        # parse_message callable calls xcom_pull(task_ids="wait_for_file_notification")
        context["ti"].xcom_pull.side_effect = None
        context["ti"].xcom_pull.return_value = json.dumps(message)
        result = parse_task.python_callable(**context)
        assert result["status"] == "success"
        assert result["entity"] == "customers"
        assert result["extract_date"] == "20260317"

    def test_parse_message_non_ok_file_skipped(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        parse_task = next(t for t in dag.tasks if t.task_id == "parse_message")
        message = {"name": "generic/customers/generic_customers_20260317.csv", "bucket": "test-bucket"}
        import json
        context = _make_context()
        context["ti"].xcom_pull.side_effect = None
        context["ti"].xcom_pull.return_value = json.dumps(message)
        result = parse_task.python_callable(**context)
        assert result["status"] == "skip"
        assert result["reason"] == "not_ok_file"

    def test_parse_message_no_messages(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        parse_task = next(t for t in dag.tasks if t.task_id == "parse_message")
        context = _make_context()
        context["ti"].xcom_pull.return_value = None
        result = parse_task.python_callable(**context)
        assert result["status"] == "no_message"

    def test_parse_message_extracts_extract_date(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pubsub_trigger_dag"]
        parse_task = next(t for t in dag.tasks if t.task_id == "parse_message")
        message = {"name": "generic/accounts/generic_accounts_20260101.ok", "bucket": "b"}
        import json
        context = _make_context()
        context["ti"].xcom_pull.side_effect = None
        context["ti"].xcom_pull.return_value = json.dumps(message)
        result = parse_task.python_callable(**context)
        assert result["extract_date"] == "20260101"


# =============================================================================
# Ingestion DAG callable logic
# =============================================================================

class TestIngestionCallables:
    def test_check_ready_fdp_models_all_loaded(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_ingestion_dag"]
        check_task = next(t for t in dag.tasks if t.task_id == "check_ready_fdp_models")

        file_metadata = {"extract_date": "20260317", "entity": "customers"}
        context = _make_context(dag_run_conf={"file_metadata": file_metadata})

        with patch("gcp_pipeline_orchestration.factories.dag_factory.EntityDependencyChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.get_loaded_entities.return_value = ["customers", "accounts"]
            mock_checker_cls.return_value = mock_checker

            check_task.python_callable(**context)

        xcom_push_calls = {
            call_args[1]["key"]: call_args[1]["value"]
            for call_args in context["ti"].xcom_push.call_args_list
        }
        assert "event_transaction_excess" in xcom_push_calls["ready_fdp_models"]
        assert "portfolio_account_excess" in xcom_push_calls["ready_fdp_models"]

    def test_check_ready_fdp_models_partial_load(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_ingestion_dag"]
        check_task = next(t for t in dag.tasks if t.task_id == "check_ready_fdp_models")

        file_metadata = {"extract_date": "20260317", "entity": "accounts"}
        context = _make_context(dag_run_conf={"file_metadata": file_metadata})

        with patch("gcp_pipeline_orchestration.factories.dag_factory.EntityDependencyChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            # Only accounts loaded — event_transaction_excess needs customers too
            mock_checker.get_loaded_entities.return_value = ["accounts"]
            mock_checker_cls.return_value = mock_checker

            check_task.python_callable(**context)

        xcom_push_calls = {
            call_args[1]["key"]: call_args[1]["value"]
            for call_args in context["ti"].xcom_push.call_args_list
        }
        ready = xcom_push_calls["ready_fdp_models"]
        # portfolio_account_excess only needs accounts — should be ready
        assert "portfolio_account_excess" in ready
        # event_transaction_excess needs customers too — should NOT be ready
        assert "event_transaction_excess" not in ready

    def test_check_ready_fdp_models_none_loaded(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_ingestion_dag"]
        check_task = next(t for t in dag.tasks if t.task_id == "check_ready_fdp_models")

        file_metadata = {"extract_date": "20260317"}
        context = _make_context(dag_run_conf={"file_metadata": file_metadata})

        with patch("gcp_pipeline_orchestration.factories.dag_factory.EntityDependencyChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.get_loaded_entities.return_value = []
            mock_checker_cls.return_value = mock_checker

            check_task.python_callable(**context)

        xcom_push_calls = {
            call_args[1]["key"]: call_args[1]["value"]
            for call_args in context["ti"].xcom_push.call_args_list
        }
        assert xcom_push_calls["ready_fdp_models"] == []


# =============================================================================
# Transformation DAG callable logic
# =============================================================================

class TestTransformationCallables:
    def test_verify_dependencies_satisfied(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_transformation_dag"]
        verify_task = next(t for t in dag.tasks if t.task_id == "verify_model_dependencies")

        context = _make_context(dag_run_conf={
            "fdp_model": "event_transaction_excess",
            "extract_date": "20260317",
        })

        with patch("gcp_pipeline_orchestration.factories.dag_factory.EntityDependencyChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.all_entities_loaded.return_value = True
            mock_checker_cls.return_value = mock_checker

            result = verify_task.python_callable(**context)

        assert result == "create_fdp_job_record"

    def test_verify_dependencies_missing(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_transformation_dag"]
        verify_task = next(t for t in dag.tasks if t.task_id == "verify_model_dependencies")

        context = _make_context(dag_run_conf={
            "fdp_model": "event_transaction_excess",
            "extract_date": "20260317",
        })

        with patch("gcp_pipeline_orchestration.factories.dag_factory.EntityDependencyChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.all_entities_loaded.return_value = False
            mock_checker.get_missing_entities.return_value = ["customers"]
            mock_checker_cls.return_value = mock_checker

            result = verify_task.python_callable(**context)

        assert result == "handle_dependency_failure"

    def test_verify_unknown_fdp_model(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_transformation_dag"]
        verify_task = next(t for t in dag.tasks if t.task_id == "verify_model_dependencies")

        context = _make_context(dag_run_conf={
            "fdp_model": "nonexistent_model",
            "extract_date": "20260317",
        })

        result = verify_task.python_callable(**context)
        assert result == "handle_dependency_failure"

    def test_verify_missing_fdp_model_key(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_transformation_dag"]
        verify_task = next(t for t in dag.tasks if t.task_id == "verify_model_dependencies")

        context = _make_context(dag_run_conf={"extract_date": "20260317"})

        result = verify_task.python_callable(**context)
        assert result == "handle_dependency_failure"


# =============================================================================
# Status DAG callable logic
# =============================================================================

class TestPipelineStatusCallables:
    def _get_status_callable(self, system_config, mock_airflow_variable):
        ns = {}
        create_dags(system_config, ns)
        dag = ns["generic_pipeline_status_dag"]
        return next(t for t in dag.tasks if t.task_id == "check_pipeline_status").python_callable

    def test_all_complete_no_exception(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        statuses = [
            {"entity_type": "customers", "status": "SUCCESS", "run_id": "r1"},
            {"entity_type": "accounts", "status": "SUCCESS", "run_id": "r2"},
            {"entity_type": "event_transaction_excess", "status": "SUCCESS", "run_id": "r3"},
            {"entity_type": "portfolio_account_excess", "status": "SUCCESS", "run_id": "r4"},
        ]

        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = statuses
            mock_repo_cls.return_value = mock_repo

            # Should not raise
            fn(**context)

    def test_missing_entity_raises(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        # customers missing from results
        statuses = [
            {"entity_type": "accounts", "status": "SUCCESS", "run_id": "r1"},
            {"entity_type": "event_transaction_excess", "status": "SUCCESS", "run_id": "r2"},
            {"entity_type": "portfolio_account_excess", "status": "SUCCESS", "run_id": "r3"},
        ]

        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = statuses
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(Exception, match="customers"):
                fn(**context)

    def test_failed_entity_raises(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        statuses = [
            {"entity_type": "customers", "status": "FAILED", "run_id": "r1"},
            {"entity_type": "accounts", "status": "SUCCESS", "run_id": "r2"},
            {"entity_type": "event_transaction_excess", "status": "SUCCESS", "run_id": "r3"},
            {"entity_type": "portfolio_account_excess", "status": "SUCCESS", "run_id": "r4"},
        ]

        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = statuses
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(Exception, match="FAILED"):
                fn(**context)

    def test_missing_fdp_model_raises(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        # All ODP entities present but FDP models missing
        statuses = [
            {"entity_type": "customers", "status": "SUCCESS", "run_id": "r1"},
            {"entity_type": "accounts", "status": "SUCCESS", "run_id": "r2"},
        ]

        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = statuses
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(Exception, match="event_transaction_excess"):
                fn(**context)

    def test_failed_fdp_model_raises(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        statuses = [
            {"entity_type": "customers", "status": "SUCCESS", "run_id": "r1"},
            {"entity_type": "accounts", "status": "SUCCESS", "run_id": "r2"},
            {"entity_type": "event_transaction_excess", "status": "FAILED", "run_id": "r3"},
            {"entity_type": "portfolio_account_excess", "status": "SUCCESS", "run_id": "r4"},
        ]

        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = statuses
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(Exception, match="event_transaction_excess"):
                fn(**context)

    def test_multiple_issues_all_in_exception(self, system_config, mock_airflow_variable):
        fn = self._get_status_callable(system_config, mock_airflow_variable)
        context = _make_context(ds_nodash="20260317")

        # Everything missing
        with patch("gcp_pipeline_orchestration.factories.dag_factory.JobControlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_entity_status.return_value = []
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(Exception) as exc_info:
                fn(**context)

        msg = str(exc_info.value)
        assert "customers" in msg
        assert "accounts" in msg
        assert "event_transaction_excess" in msg
        assert "portfolio_account_excess" in msg

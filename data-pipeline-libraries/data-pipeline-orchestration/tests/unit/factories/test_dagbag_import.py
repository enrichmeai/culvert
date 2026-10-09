"""The rendered DAGs load in Airflow's own DagBag with no import errors (#54).

``test_create_dags.py`` asserts on the DAG objects ``create_dags`` returns. This
goes one step further: it writes the DAG entrypoint file the README documents
into a DAG folder, next to a ``system.yaml``, and has Airflow's ``DagBag`` parse
that folder the way the scheduler does. That catches what a structural test
cannot: an entrypoint that raises at import, or one Airflow skips.

``Variable.get`` is patched to return its default, so no metadata database is
needed; the DAGs are parsed, never run.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("airflow", reason="apache-airflow required for the DagBag test")

from airflow.models import DagBag  # noqa: E402

# The entrypoint as the README documents it. Its first line names Airflow: in safe
# mode the DagBag only parses files that contain both "airflow" and "dag".
ENTRYPOINT = textwrap.dedent(
    """\
    # The Airflow DAG entrypoint for the generic system.
    from pathlib import Path
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    create_dags(Path(__file__).parent / "config" / "system.yaml", globals())
    """
)

SYSTEM_YAML = textwrap.dedent(
    """\
    system_id: GENERIC
    system_name: Generic
    file_prefix: generic
    trigger_schedule: "*/5 * * * *"
    environment: int
    entities:
      customers: {description: Customer records}
      accounts: {description: Account records}
    fdp_models:
      customer_account:
        requires: [customers, accounts]
        description: Joined customer-account FDP
    infrastructure:
      pubsub: {subscription: "projects/{project_id}/subscriptions/generic-landing-sub"}
      datasets: {odp: "odp_{system}", fdp: "fdp_{system}"}
      buckets: {error: "{project_id}-generic-error", temp: "{project_id}-generic-temp"}
    """
)

EXPECTED_DAG_IDS = {
    "generic_pubsub_trigger_dag",
    "generic_customers_ingestion_dag",
    "generic_accounts_ingestion_dag",
    "generic_customer_account_transformation_dag",
    "generic_pipeline_status_dag",
}


def _variable_default(key, default_var=None, **kwargs):
    return default_var


@pytest.fixture
def dag_folder(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "system.yaml").write_text(SYSTEM_YAML)
    (tmp_path / "generic_pipeline.py").write_text(ENTRYPOINT)
    return tmp_path


def _parse(folder) -> DagBag:
    with patch("airflow.models.Variable.get", side_effect=_variable_default):
        return DagBag(dag_folder=str(folder), include_examples=False, safe_mode=True)


def test_the_documented_entrypoint_loads_with_no_import_errors(dag_folder):
    bag = _parse(dag_folder)

    assert bag.import_errors == {}
    assert set(bag.dag_ids) == EXPECTED_DAG_IDS


def test_every_dag_has_tasks_and_is_attributed_to_the_entrypoint(dag_folder):
    bag = _parse(dag_folder)

    for dag_id in EXPECTED_DAG_IDS:
        dag = bag.dags[dag_id]  # not get_dag(), which reads the metadata database
        assert dag.tasks, f"{dag_id} has no tasks"
        assert Path(dag.fileloc).resolve() == (dag_folder / "generic_pipeline.py").resolve()


def test_a_broken_system_yaml_is_reported_as_an_import_error(dag_folder):
    (dag_folder / "config" / "system.yaml").write_text("system_name: Generic\n")

    bag = _parse(dag_folder)

    assert bag.dag_ids == []
    (error,) = bag.import_errors.values()
    assert "system.yaml missing required keys" in error


@pytest.mark.parametrize("form", ["path", "str", "system_config", "dict"])
def test_create_dags_takes_each_documented_form_of_config(dag_folder, form):
    import yaml

    from data_pipeline_orchestration.factories.config import load_system_config
    from data_pipeline_orchestration.factories.dag_factory import create_dags

    path = dag_folder / "config" / "system.yaml"
    config = {
        "path": path,
        "str": str(path),
        "system_config": load_system_config(path),
        "dict": yaml.safe_load(SYSTEM_YAML),
    }[form]
    namespace = {}
    with patch("airflow.models.Variable.get", side_effect=_variable_default):
        create_dags(config, namespace)

    assert set(namespace) == EXPECTED_DAG_IDS

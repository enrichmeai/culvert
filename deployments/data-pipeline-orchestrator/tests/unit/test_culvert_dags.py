"""Culvert orchestrator wiring tests.

Verify the deployment builds its DAG set from `config/system.yaml` via the
Culvert `data-pipeline-orchestration` library — one ingestion DAG per entity,
one transformation DAG per FDP model, plus the cross-cutting DAGs.

Airflow-free: when Airflow is not installed the library returns lightweight
stub DAGs carrying their `dag_id`, so we assert the wiring (names/counts)
without needing an Airflow runtime. Full DAG-parse validation happens in the
deploy-and-test phase (Composer/Airflow).
"""

from pathlib import Path

from data_pipeline_orchestration.factories import DagFactory

CONFIG = Path(__file__).resolve().parents[2] / "config" / "system.yaml"

# Ground truth from config/system.yaml.
ENTITIES = {"customers", "accounts", "decision", "applications"}
FDP_MODELS = {
    "event_transaction_excess",   # join: customers + accounts
    "portfolio_account_excess",   # map: decision
    "portfolio_account_facility", # map: applications
}


def _factory() -> DagFactory:
    return DagFactory.from_config(CONFIG)


def test_config_loads_expected_entities_and_fdp_models() -> None:
    f = _factory()
    assert set(f.entity_names()) == ENTITIES
    assert set(f.fdp_models().keys()) == FDP_MODELS


def test_one_ingestion_dag_per_entity() -> None:
    f = _factory()
    names = {name for name, _dag in f.ingestion_dags()}
    assert names == ENTITIES


def test_one_transformation_dag_per_fdp_model() -> None:
    f = _factory()
    dags = list(f.transformation_dags())
    assert len(dags) == len(FDP_MODELS)


def test_fdp_dependency_shapes_preserved() -> None:
    """JOIN requires >1 entity; MAP requires exactly 1 — carried from config."""
    f = _factory()
    models = f.fdp_models()
    assert models["event_transaction_excess"]["type"] == "join"
    assert set(models["event_transaction_excess"]["requires"]) == {"customers", "accounts"}
    assert models["portfolio_account_excess"]["type"] == "map"
    assert models["portfolio_account_excess"]["requires"] == ["decision"]


def test_cross_cutting_dags_build() -> None:
    f = _factory()
    for dag in (f.pubsub_trigger_dag(), f.error_handling_dag(), f.status_dag()):
        assert dag is not None
        assert getattr(dag, "dag_id", None)

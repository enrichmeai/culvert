# Culvert orchestration — config-driven DAGs.
#
# The predecessor deployment shipped ~8,000 lines of hand-rolled DAG codegen
# (generate_dags.py + eleven generated static DAG files) with the old framework's
# bespoke observability/audit stack baked in as string templates. On Culvert that
# collapses to this: the DAG-building lives in the `data-pipeline-orchestration`
# library (DagFactory + Dataflow operators + Pub/Sub sensors + error-handling
# callbacks + the JOIN/MAP EntityDependencyChecker), driven from `system.yaml`.
#
# Airflow discovers DAGs by scanning module globals(), so this file loads the
# factory and publishes the DAG objects it produces:
#   - one ingestion DAG per entity      (Pub/Sub sense -> Dataflow -> reconcile)
#   - one transformation DAG per FDP    (dependency gate -> dbt)
#   - the pub/sub trigger, error-handling, and status DAGs
#
# The ingestion Dataflow tasks target the Culvert Java Dataflow deployment
# (`original-data-to-bigqueryload-java`); transformation targets the dbt
# deployment. Nothing here is on PyPI yet — the library is installed from source
# until the coordinated 0.1.0 release (see docs/framework-evolution/13).

from pathlib import Path

from data_pipeline_orchestration.factories import DagFactory

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "system.yaml"

factory = DagFactory.from_config(_CONFIG)

# Entity ingestion DAGs.
for _name, _dag in factory.ingestion_dags():
    globals()[f"ingestion_{_name}"] = _dag

# FDP transformation DAGs (JOIN/MAP dependency gating from `fdp_models`).
for _dag in factory.transformation_dags():
    globals()[getattr(_dag, "dag_id", "transformation")] = _dag

# Cross-cutting DAGs.
globals()["pubsub_trigger"] = factory.pubsub_trigger_dag()
globals()["error_handling"] = factory.error_handling_dag()
globals()["status"] = factory.status_dag()

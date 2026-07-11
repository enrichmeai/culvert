"""
Config-driven DAG factory entrypoint for the Culvert orchestration port.

``create_dags(config, globals())`` reads a parsed ``system.yaml`` config dict
(the shape returned by :func:`data_pipeline_orchestration.factories.config`)
and injects the full set of pipeline DAGs into the caller's module namespace so
Airflow's DagBag discovers them. Four DAG *types* are produced:

  1. ``{system_id}_pubsub_trigger_dag`` -- listens for ``.ok`` files via the
     T11.2b :class:`BasePubSubPullSensor`, then triggers the matching
     per-entity ingestion DAG.
  2. ``{system_id}_{entity}_ingestion_dag`` (one per entity) -- runs Dataflow
     via the T11.2b :class:`BaseDataflowOperator`, checks FDP readiness with
     the T11.2b :class:`EntityDependencyChecker`, and triggers ready
     transformation DAGs.
  3. ``{system_id}_{fdp_model}_transformation_dag`` (one per FDP model) --
     runs dbt (staging → fdp → tests) for the model once its required ODP
     entities are loaded. (T11.2d / #87)
  4. ``{system_id}_pipeline_status_dag`` -- daily observer that alerts if the
     pipeline is incomplete for the day. (T11.2d / #87)

Each DAG carries the global :func:`on_failure_callback` (DLQ/quarantine router)
in its ``default_args`` so failed tasks are routed to the Dead Letter Queue.

The ``{system_id}_error_handling_dag`` (a 5th builder, periodic recovery) is
reachable via :class:`DagFactory.error_handling_dag` but is intentionally NOT
wired into ``create_dags`` — #87's acceptance gate is the 4-type set above
(the 2 ingestion-side types from #86 plus transformation + pipeline_status).

This module is import-safe **without** Airflow installed: the heavy
lifting is delegated to
:mod:`data_pipeline_orchestration.factories._dag_builders`, whose builders
lazy-import Airflow inside the function body and raise a clear ``ImportError``
when it is absent.

Usage (in any DAG entrypoint file under ``dags/``)::

    from data_pipeline_orchestration.factories.dag_factory import create_dags
    from data_pipeline_orchestration.factories.config import load_system_config

    config = load_system_config()          # reads system.yaml
    create_dags(config, globals())         # injects the ingestion-side DAGs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ._dag_builders import (
    build_ingestion_dag,
    build_pubsub_trigger_dag,
    build_status_dag,
    build_transformation_dag,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers (pure; no Airflow, no cloud SDKs)
# =============================================================================

def _entity_names(config: Dict[str, Any]) -> List[str]:
    """Sorted entity names from the config (deterministic ordering)."""
    return sorted((config.get("entities") or {}).keys())


def _fdp_dependencies(config: Dict[str, Any]) -> Dict[str, List[str]]:
    """Map each FDP model to the entities it requires."""
    return {
        model: list(info.get("requires", []))
        for model, info in (config.get("fdp_models") or {}).items()
    }


def _system_id(config: Dict[str, Any]) -> str:
    return str(config.get("system_id", "generic")).lower()


# =============================================================================
# Entrypoint
# =============================================================================

def create_dags(config: Dict[str, Any], global_ns: Dict[str, Any]) -> None:
    """Build the full DAG set and inject it into ``global_ns``.

    For a config with N entities and M FDP models this registers
    ``2 + N + M`` DAGs spanning **four** DAG types:

      * one ``{system_id}_pubsub_trigger_dag``
      * one ``{system_id}_{entity}_ingestion_dag`` per entity
      * one ``{system_id}_{fdp_model}_transformation_dag`` per FDP model
      * one ``{system_id}_pipeline_status_dag``

    Parameters
    ----------
    config:
        Parsed ``system.yaml`` dict (as returned by ``load_system_config``).
    global_ns:
        The caller's ``globals()`` dict. DAG objects are assigned into it under
        their ``dag_id`` so Airflow's DagBag discovers them.

    Notes
    -----
    Delegates DAG construction to ``_dag_builders`` (which composes the T11.2b
    sensor / operator / dependency-checker and the #87 callbacks). The
    periodic ``error_handling`` DAG is reachable via ``DagFactory`` but is not
    wired here (see module docstring).
    """
    system_id = _system_id(config)
    entities = _entity_names(config)
    fdp_models = sorted((config.get("fdp_models") or {}).keys())

    # DAG type 1: pub/sub trigger (one per system)
    trigger_dag = build_pubsub_trigger_dag(config)
    global_ns[trigger_dag.dag_id] = trigger_dag
    logger.info("Registered pubsub trigger DAG: %s", trigger_dag.dag_id)

    # DAG type 2: one ingestion DAG per entity
    entity_cfgs = config.get("entities") or {}
    for entity in entities:
        ingestion_dag = build_ingestion_dag(entity, entity_cfgs.get(entity) or {}, config)
        global_ns[ingestion_dag.dag_id] = ingestion_dag
        logger.info("Registered ingestion DAG: %s", ingestion_dag.dag_id)

    # DAG type 3: one transformation DAG per FDP model (#87)
    fdp_cfgs = config.get("fdp_models") or {}
    for model in fdp_models:
        transformation_dag = build_transformation_dag(model, fdp_cfgs.get(model) or {}, config)
        global_ns[transformation_dag.dag_id] = transformation_dag
        logger.info("Registered transformation DAG: %s", transformation_dag.dag_id)

    # DAG type 4: pipeline status observer (one per system) (#87)
    status_dag = build_status_dag(config)
    global_ns[status_dag.dag_id] = status_dag
    logger.info("Registered pipeline status DAG: %s", status_dag.dag_id)

    logger.info(
        "create_dags wired %d DAGs (4 types) for system '%s'",
        2 + len(entities) + len(fdp_models),
        system_id,
    )


__all__ = ["create_dags"]

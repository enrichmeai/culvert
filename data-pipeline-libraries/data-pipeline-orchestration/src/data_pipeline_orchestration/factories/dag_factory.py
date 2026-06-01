"""
Config-driven DAG factory entrypoint for the Culvert orchestration port.

``create_dags(config, globals())`` reads a parsed ``system.yaml`` config dict
(the shape returned by :func:`data_pipeline_orchestration.factories.config`)
and injects the *ingestion-side* DAGs into the caller's module namespace so
Airflow's DagBag discovers them:

  1. ``{system_id}_pubsub_trigger_dag`` -- listens for ``.ok`` files via the
     T11.2b :class:`BasePubSubPullSensor`, then triggers the matching
     per-entity ingestion DAG.
  2. ``{system_id}_{entity}_ingestion_dag`` (one per entity) -- runs Dataflow
     via the T11.2b :class:`BaseDataflowOperator`, checks FDP readiness with
     the T11.2b :class:`EntityDependencyChecker`, and triggers ready
     transformation DAGs.

The transformation / status / error-handling DAGs and the global callbacks are
owned by ticket #87 and are intentionally NOT wired here.

This module is import-safe **without** Airflow installed and **without** the
legacy ``gcp_pipeline_core`` package: the heavy lifting is delegated to
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

from ._dag_builders import build_ingestion_dag, build_pubsub_trigger_dag

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers (pure; no Airflow / no gcp_pipeline_core)
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
    """Build the ingestion-side DAGs and inject them into ``global_ns``.

    For a config with N entities this registers ``1 + N`` DAGs:

      * one ``{system_id}_pubsub_trigger_dag``
      * one ``{system_id}_{entity}_ingestion_dag`` per entity

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
    sensor / operator / dependency-checker). Transformation, status and
    error-handling DAGs are #87's scope and are not created here.
    """
    system_id = _system_id(config)
    entities = _entity_names(config)

    # DAG 1: pub/sub trigger (one per system)
    trigger_dag = build_pubsub_trigger_dag(config)
    global_ns[trigger_dag.dag_id] = trigger_dag
    logger.info("Registered pubsub trigger DAG: %s", trigger_dag.dag_id)

    # DAG 2..N+1: one ingestion DAG per entity
    entity_cfgs = config.get("entities") or {}
    for entity in entities:
        ingestion_dag = build_ingestion_dag(entity, entity_cfgs.get(entity) or {}, config)
        global_ns[ingestion_dag.dag_id] = ingestion_dag
        logger.info("Registered ingestion DAG: %s", ingestion_dag.dag_id)

    logger.info(
        "create_dags wired %d ingestion-side DAGs for system '%s'",
        1 + len(entities),
        system_id,
    )


__all__ = ["create_dags"]

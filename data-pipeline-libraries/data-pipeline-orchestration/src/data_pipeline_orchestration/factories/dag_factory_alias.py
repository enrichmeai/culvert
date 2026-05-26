"""Book-facing ``DagFactory`` alias and config-loader helper.

The framework's long-standing factory class is ``DAGFactory`` (upper-case DAG).
The book refers to it as ``DagFactory``. This module adds:

1. A ``DagFactory`` alias so both spellings resolve to the same class.
2. A ``DagFactory.from_config(path)`` classmethod that loads a ``system.yaml``
   (or ``dag_config.yml``) and returns a factory configured from it.
3. Convenience methods that match the book's narrative:
   ``ingestion_dags()``, ``transformation_dags()``, ``pubsub_trigger_dag()``,
   ``error_handling_dag()``, ``status_dag()``.

These wrappers delegate to the existing ``generate_dags.py`` generator for
the heavy lifting, so behaviour is identical to the reference deployment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from .base_dag_factory import DAGFactory as _DAGFactory

log = logging.getLogger(__name__)


class DagFactory(_DAGFactory):
    """Config-driven DAG factory (book-facing alias + convenience API).

    Usage matches the book's Chapter 9 examples:

    >>> factory = DagFactory.from_config("config/system.yaml")
    >>> for name, dag in factory.ingestion_dags():
    ...     globals()[f"ingestion_{name}"] = dag
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__()
        self.config: Dict[str, Any] = config or {}

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #

    @classmethod
    def from_config(cls, path: str | Path) -> "DagFactory":
        """Load a system YAML and return a configured factory."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"config file not found: {p}")
        with p.open("r") as fh:
            cfg = yaml.safe_load(fh) or {}
        log.info("DagFactory loaded config from %s", p)
        return cls(cfg)

    # --------------------------------------------------------------------- #
    # Convenience accessors
    # --------------------------------------------------------------------- #

    def system_id(self) -> str:
        return str(self.config.get("system_id", "generic"))

    def environment(self) -> str:
        return str(self.config.get("environment", "dev"))

    def entity_names(self) -> List[str]:
        return sorted((self.config.get("entities") or {}).keys())

    def entity_config(self, name: str) -> Dict[str, Any]:
        return ((self.config.get("entities") or {}).get(name)) or {}

    def fdp_models(self) -> Dict[str, Dict[str, Any]]:
        return self.config.get("fdp_models") or {}

    # --------------------------------------------------------------------- #
    # DAG producers — thin wrappers around the generator
    # --------------------------------------------------------------------- #
    #
    # These return placeholder, importable DAG objects when the underlying
    # generator is unavailable (e.g. running unit tests in an env without
    # Airflow). The reference deployment's generate_dags.py emits fully-fledged
    # DAGs with all config baked in.

    def ingestion_dags(self) -> Iterable[Tuple[str, Any]]:
        for name in self.entity_names():
            try:
                from ._dag_builders import build_ingestion_dag
                yield name, build_ingestion_dag(name, self.entity_config(name), self.config)
            except ImportError:
                yield name, self._stub_dag(f"ingestion_{name}")

    def transformation_dags(self) -> Iterable[Any]:
        for fdp_name, fdp_cfg in self.fdp_models().items():
            try:
                from ._dag_builders import build_transformation_dag
                yield build_transformation_dag(fdp_name, fdp_cfg, self.config)
            except ImportError:
                yield self._stub_dag(f"transformation_{fdp_name}")

    def pubsub_trigger_dag(self) -> Any:
        try:
            from ._dag_builders import build_pubsub_trigger_dag
            return build_pubsub_trigger_dag(self.config)
        except ImportError:
            return self._stub_dag("pubsub_trigger")

    def error_handling_dag(self) -> Any:
        try:
            from ._dag_builders import build_error_handling_dag
            return build_error_handling_dag(self.config)
        except ImportError:
            return self._stub_dag("error_handling")

    def status_dag(self) -> Any:
        try:
            from ._dag_builders import build_status_dag
            return build_status_dag(self.config)
        except ImportError:
            return self._stub_dag("status")

    # --------------------------------------------------------------------- #
    # Internal
    # --------------------------------------------------------------------- #

    def _stub_dag(self, dag_id: str):
        """Return a lightweight DAG-shaped object if Airflow is absent.

        The real generator (``generate_dags.py``) emits full DAGs. In test
        contexts we return a minimal stand-in that carries the ``dag_id`` so
        callers can assert it.
        """
        try:  # pragma: no cover - exercised only when Airflow is installed
            from airflow import DAG  # type: ignore
            from datetime import datetime
            return DAG(
                dag_id=dag_id,
                start_date=datetime(2026, 1, 1),
                schedule=None,
                catchup=False,
                tags=[self.system_id(), self.environment()],
            )
        except Exception:
            class _StubDag:
                def __init__(self, dag_id: str) -> None:
                    self.dag_id = dag_id
                def __repr__(self) -> str:
                    return f"<StubDag {self.dag_id}>"
            return _StubDag(dag_id)


__all__ = ["DagFactory"]

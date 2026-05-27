"""Stage 3 auto-config registry — Python equivalent of the Java AutoConfig.

Discovers Culvert contract implementations on the import path via Python's
``importlib.metadata.entry_points`` and exposes typed lookup methods.

Each cloud module (``data-pipeline-gcp-bigquery``, ``data-pipeline-gcp-gcs``,
...) declares its implementations under the ``data_pipeline_core.adapters``
entry-point group in its ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."data_pipeline_core.adapters"]
    warehouse = "data_pipeline_gcp_bigquery:BigQueryWarehouse"
    blob_store = "data_pipeline_gcp_gcs:GcsBlobStore"

The registry imports the named class (no instantiation — most adapters
need constructor arguments). Consumers retrieve the class and instantiate
explicitly, or use the upcoming sprint-5 config-driven layer to wire
arguments automatically.

Sprint-4 deliverable.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "data_pipeline_core.adapters"


@dataclass
class AutoConfig:
    """Lookup table of contract -> impl-class entries discovered on the
    import path.

    Field names match the contract module names in
    ``data_pipeline_core.contracts.*`` (warehouse, blob_store, source, sink,
    transform, secrets, job_control, finops, observability, lineage,
    audit, governance, pipeline, runtime).
    """

    warehouse: List[Type[Any]] = field(default_factory=list)
    blob_store: List[Type[Any]] = field(default_factory=list)
    source: List[Type[Any]] = field(default_factory=list)
    sink: List[Type[Any]] = field(default_factory=list)
    transform: List[Type[Any]] = field(default_factory=list)
    secrets: List[Type[Any]] = field(default_factory=list)
    job_control: List[Type[Any]] = field(default_factory=list)
    finops: List[Type[Any]] = field(default_factory=list)
    observability: List[Type[Any]] = field(default_factory=list)
    lineage: List[Type[Any]] = field(default_factory=list)
    audit: List[Type[Any]] = field(default_factory=list)
    governance: List[Type[Any]] = field(default_factory=list)
    pipeline: List[Type[Any]] = field(default_factory=list)
    runtime: List[Type[Any]] = field(default_factory=list)

    # In-process registration table — overrides anything from entry points.
    # Filled by the @register_adapter decorator below.
    _process_overrides: Dict[str, List[Type[Any]]] = field(default_factory=dict)

    def first(self, name: str) -> Optional[Type[Any]]:
        """Return the first registered impl class for ``name``, or None."""
        impls = self.all(name)
        return impls[0] if impls else None

    def all(self, name: str) -> List[Type[Any]]:
        """Return all registered impl classes for ``name``."""
        # In-process overrides first; then entry-point discoveries.
        return list(self._process_overrides.get(name, [])) + list(getattr(self, name, []))


# Module-level shared registry (process overrides accumulate here).
_REGISTRY: AutoConfig = AutoConfig()


def discover() -> AutoConfig:
    """Build a fresh AutoConfig by walking ``importlib.metadata.entry_points``.

    Re-importable: each call re-reads the entry points (useful if a plugin
    is installed at runtime).
    """
    config = AutoConfig()
    config._process_overrides = dict(_REGISTRY._process_overrides)
    eps = entry_points()
    # Python 3.10+ entry_points() returns a SelectableGroups; .select() for
    # 3.10+, fallback to dict-style for older.
    try:
        group_entries = eps.select(group=ENTRY_POINT_GROUP)
    except AttributeError:
        group_entries = eps.get(ENTRY_POINT_GROUP, [])

    for ep in group_entries:
        try:
            cls = ep.load()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load entry-point %s = %s: %s",
                ep.name, ep.value, exc,
            )
            continue
        # Entry-point name maps directly to AutoConfig field.
        field_list = getattr(config, ep.name, None)
        if field_list is None:
            logger.warning("Unknown adapter contract '%s' (entry-point=%s)", ep.name, ep.value)
            continue
        field_list.append(cls)
    return config


def register_adapter(contract_name: str):
    """Decorator that registers ``cls`` as an impl of ``contract_name``
    in the process-wide registry.

    Useful for in-process registration (testing, demos) where you don't
    want to package the impl as a separate distribution.

    .. code-block:: python

        from data_pipeline_core.autoconfig import register_adapter

        @register_adapter("warehouse")
        class MyTestWarehouse:
            def query(self, sql, params=None): ...
            ...
    """
    def decorator(cls):
        _REGISTRY._process_overrides.setdefault(contract_name, []).append(cls)
        return cls

    return decorator


def reset_process_registry() -> None:
    """Clear the process-wide registry. For tests."""
    _REGISTRY._process_overrides.clear()

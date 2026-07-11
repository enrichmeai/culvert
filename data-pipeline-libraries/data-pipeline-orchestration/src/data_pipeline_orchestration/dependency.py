"""
Entity Dependency Checker.

Library provides the MECHANISM for checking entity dependencies.
Pipelines provide their own CONFIGURATION.

The library is GENERIC - no system specific configuration.
Each pipeline defines its own entity dependencies.

Usage:
    # In pipeline DAG (e.g., deployments/application1-orchestration/dags/application1_fdp_transform_dag.py)
    from data_pipeline_orchestration import EntityDependencyChecker

    # Pipeline defines its configuration
    checker = EntityDependencyChecker(
        project_id="my-project",
        system_id="application1",
        required_entities=["customers", "accounts", "decision"]
    )

    if checker.all_entities_loaded(extract_date):
        trigger_transformation()
"""

import logging
from datetime import date
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Job-control coupling (T11.2b — CLOSED for the 0.1.0 publish)
#
# The default reader is Culvert's own ``._job_control.BigQueryJobControl``
# (lazy google-cloud-bigquery). Injectable seam:
#   - Repository protocol:
#       data_pipeline_core.contracts.job_control.JobControlRepository
#       (runtime_checkable Protocol, 11 methods, no GCP-type leakage)
#   - Status enum:
#       data_pipeline_core.job_control_api.types.JobStatus
#       (str-Enum; values are lowercase, e.g. SUCCEEDED = "succeeded")
#
# Migration notes:
#   1. The legacy JobStatus.SUCCESS = "SUCCESS" (uppercase) while the Culvert
#      enum uses SUCCEEDED = "succeeded". The comparison in
#      get_loaded_entities() uses s["status"] == _SUCCESS_STATUS which is
#      set to the legacy uppercase value here. When the concrete BigQuery
#      adapter migrates to data_pipeline_core, this constant must change
#      to match the new value (or the adapter normalises it before returning).
#   2. The legacy get_entity_status() returns List[dict]. The Culvert
#      Protocol's return type is List[EntityStatus] (TypedDict) — same
#      shape, dict-compatible, so s["entity_type"] / s["status"] still work.
#   3. The fallback path (no job_repo injected) previously instantiated
#      JobControlRepository(project_id, ...) which imports google-cloud-bigquery
#      at construction time. Replaced with NotImplementedError so the library
#      does not pull in GCP SDK at import time. The caller (DAG / pipeline)
#      is responsible for injecting a concrete implementation.
# ---------------------------------------------------------------------------

# SUCCESS status string — Culvert wire value (JobStatus.SUCCEEDED in both the
# Java and Python cores; the Java BigQueryJobControlRepository stores this).
_SUCCESS_STATUS: str = "succeeded"

logger = logging.getLogger(__name__)


class EntityDependencyChecker:
    """
    Generic entity dependency checker.

    Library provides the mechanism only. Pipeline provides:
    - project_id: GCP project
    - system_id: System identifier (e.g., "application1", "application2", "any_system")
    - required_entities: List of entity names that must all be loaded

    No hardcoded system configurations in the library.

    The ``job_repo`` argument must satisfy the contract defined by
    ``data_pipeline_core.contracts.job_control.JobControlRepository``
    (a ``runtime_checkable`` Protocol).  Callers inject the concrete
    BigQuery-backed adapter; the library itself does not import
    ``google-cloud-bigquery`` at module load time (the default
    ``._job_control.BigQueryJobControl`` reader imports it lazily on first
    query).

    Example:
        >>> checker = EntityDependencyChecker(
        ...     project_id="my-project",
        ...     system_id="application1",
        ...     required_entities=["customers", "accounts", "decision"]
        ... )
        >>> if checker.all_entities_loaded(date(2026, 1, 1)):
        ...     trigger_transformation()
    """

    def __init__(
        self,
        project_id: str,
        system_id: str,
        required_entities: List[str],
        job_control_dataset: str = "job_control",
        job_control_table: str = "pipeline_jobs",
        job_repo: Optional[Any] = None,
    ):
        """
        Initialize dependency checker.

        Args:
            project_id: GCP project ID
            system_id: System identifier (pipeline provides this)
            required_entities: List of entity types that must all be loaded
            job_control_dataset: Dataset for job control table (used by the
                concrete adapter, not by this class directly).
            job_control_table: Table name for job control (same note).
            job_repo: Concrete job-control repository that implements
                ``get_entity_status(system_id, extract_date) -> List[dict]``.
                Must be provided by the caller (DAG or pipeline); the library
                no longer instantiates a concrete repo to avoid importing
                google-cloud-bigquery at module load time.

        Raises:
            ValueError: if no ``job_repo`` is supplied (avoids a silent
                failure path that previously imported google-cloud-bigquery).
        """
        self.project_id = project_id
        self.system_id = system_id
        self.required_entities = required_entities

        if job_repo is None:
            # Lazy import — keeps google-cloud-bigquery out of module load
            # time while preserving the original constructor contract for
            # callers that don't supply a repo (DAG factory, deployments).
            # T11.2b closed for the 0.1.0 publish: the default reader is
            # Culvert's own (_job_control), not the predecessor's.
            from ._job_control import BigQueryJobControl  # noqa: PLC0415
            job_repo = BigQueryJobControl(
                project_id,
                dataset=job_control_dataset,
                table=job_control_table,
            )
        self.job_repo = job_repo

    @property
    def required_count(self) -> int:
        """Number of entities required."""
        return len(self.required_entities)

    def get_loaded_entities(self, extract_date: date) -> List[str]:
        """
        Get list of successfully loaded entities for the extract date.

        Args:
            extract_date: Date to check

        Returns:
            List of entity types with SUCCESS status
        """
        statuses = self.job_repo.get_entity_status(self.system_id, extract_date)

        return [
            s["entity_type"].lower()
            for s in statuses
            if s["status"] == _SUCCESS_STATUS
        ]

    def all_entities_loaded(self, extract_date: date) -> bool:
        """
        Check if all required entities are loaded.

        Args:
            extract_date: Date to check

        Returns:
            True if all required entities have SUCCESS status
        """
        required = set(e.lower() for e in self.required_entities)
        loaded = set(self.get_loaded_entities(extract_date))

        all_loaded = required.issubset(loaded)

        if all_loaded:
            logger.info(
                f"All entities loaded for {self.system_id}/{extract_date}: "
                f"{list(required)}"
            )
        else:
            missing = required - loaded
            logger.info(
                f"Waiting for {self.system_id}/{extract_date} entities: "
                f"{list(missing)}"
            )

        return all_loaded

    def get_missing_entities(self, extract_date: date) -> List[str]:
        """
        Get list of entities not yet loaded.

        Args:
            extract_date: Date to check

        Returns:
            List of entity types still pending
        """
        required = set(e.lower() for e in self.required_entities)
        loaded = set(self.get_loaded_entities(extract_date))
        return list(required - loaded)

    def get_loaded_count(self, extract_date: date) -> int:
        """
        Get count of loaded entities.

        Args:
            extract_date: Date to check

        Returns:
            Number of successfully loaded entities
        """
        loaded = self.get_loaded_entities(extract_date)
        required_lower = [e.lower() for e in self.required_entities]
        return len([e for e in loaded if e in required_lower])

    def get_status_summary(self, extract_date: date) -> dict:
        """
        Get summary of entity load status.

        Args:
            extract_date: Date to check

        Returns:
            Dict with status summary
        """
        loaded = self.get_loaded_entities(extract_date)
        missing = self.get_missing_entities(extract_date)
        required_lower = [e.lower() for e in self.required_entities]

        return {
            "system_id": self.system_id,
            "extract_date": str(extract_date),
            "required_entities": self.required_entities,
            "required_count": self.required_count,
            "loaded_entities": loaded,
            "loaded_count": len([e for e in loaded if e in required_lower]),
            "missing_entities": missing,
            "all_loaded": len(missing) == 0
        }


__all__ = [
    'EntityDependencyChecker',
]


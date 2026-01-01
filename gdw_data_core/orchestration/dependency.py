"""
Entity Dependency Checker.

Validates all required entities are loaded before transformation.
"""

import logging
from datetime import date
from typing import List, Dict, Optional

from gdw_data_core.core.job_control import JobControlRepository, JobStatus

logger = logging.getLogger(__name__)


# Entity dependencies per system
SYSTEM_DEPENDENCIES: Dict[str, Dict] = {
    "em": {
        "entities": ["customers", "accounts", "decision"],
        "required_count": 3,
    },
    "loa": {
        "entities": ["applications"],
        "required_count": 1,
    },
}


class EntityDependencyChecker:
    """
    Check if all required entities are loaded for a system.

    This is used to determine when to trigger transformation pipelines
    after all source entities have been successfully loaded into ODP.

    Example:
        >>> checker = EntityDependencyChecker(project_id="my-project")
        >>> if checker.all_entities_loaded("em", date(2026, 1, 1)):
        ...     trigger_transformation()
        >>> else:
        ...     missing = checker.get_missing_entities("em", date(2026, 1, 1))
        ...     print(f"Waiting for: {missing}")

    Attributes:
        project_id: GCP project ID
        job_repo: JobControlRepository instance
        dependencies: System dependency configuration
    """

    def __init__(
        self,
        project_id: str,
        custom_dependencies: Optional[Dict] = None,
        job_repo: Optional[JobControlRepository] = None
    ):
        """
        Initialize entity dependency checker.

        Args:
            project_id: GCP project ID
            custom_dependencies: Override default system dependencies
            job_repo: Optional JobControlRepository (for testing)
        """
        self.project_id = project_id
        self.job_repo = job_repo or JobControlRepository(project_id)
        self.dependencies = custom_dependencies or SYSTEM_DEPENDENCIES

    def get_required_entities(self, system_id: str) -> List[str]:
        """
        Get list of required entities for a system.

        Args:
            system_id: System identifier (em, loa)

        Returns:
            List of entity type names

        Raises:
            ValueError: If system_id is not recognized
        """
        system_id_lower = system_id.lower()
        if system_id_lower not in self.dependencies:
            raise ValueError(f"Unknown system: {system_id}")
        return self.dependencies[system_id_lower]["entities"]

    def get_loaded_entities(
        self,
        system_id: str,
        extract_date: date
    ) -> List[str]:
        """
        Get list of successfully loaded entities.

        Args:
            system_id: System identifier
            extract_date: Extract date to check

        Returns:
            List of entity types with SUCCESS status
        """
        statuses = self.job_repo.get_entity_status(system_id.upper(), extract_date)

        return [
            s["entity_type"].lower()
            for s in statuses
            if s["status"] == JobStatus.SUCCESS.value
        ]

    def all_entities_loaded(
        self,
        system_id: str,
        extract_date: date
    ) -> bool:
        """
        Check if all required entities are loaded.

        Args:
            system_id: System identifier
            extract_date: Extract date to check

        Returns:
            True if all required entities have SUCCESS status
        """
        required = set(self.get_required_entities(system_id))
        loaded = set(self.get_loaded_entities(system_id, extract_date))

        all_loaded = required.issubset(loaded)

        if all_loaded:
            logger.info(f"All entities loaded for {system_id}/{extract_date}")
        else:
            missing = required - loaded
            logger.info(f"Waiting for entities: {missing}")

        return all_loaded

    def get_missing_entities(
        self,
        system_id: str,
        extract_date: date
    ) -> List[str]:
        """
        Get list of entities not yet loaded.

        Args:
            system_id: System identifier
            extract_date: Extract date to check

        Returns:
            List of entity types not yet successfully loaded
        """
        required = set(self.get_required_entities(system_id))
        loaded = set(self.get_loaded_entities(system_id, extract_date))
        return list(required - loaded)

    def get_dependency_status(
        self,
        system_id: str,
        extract_date: date
    ) -> Dict:
        """
        Get detailed dependency status.

        Args:
            system_id: System identifier
            extract_date: Extract date to check

        Returns:
            Dict with required, loaded, missing, and ready status
        """
        required = self.get_required_entities(system_id)
        loaded = self.get_loaded_entities(system_id, extract_date)
        missing = self.get_missing_entities(system_id, extract_date)

        return {
            "system_id": system_id,
            "extract_date": str(extract_date),
            "required": required,
            "loaded": loaded,
            "missing": missing,
            "ready": len(missing) == 0,
            "progress": f"{len(loaded)}/{len(required)}",
        }


__all__ = [
    'SYSTEM_DEPENDENCIES',
    'EntityDependencyChecker',
]


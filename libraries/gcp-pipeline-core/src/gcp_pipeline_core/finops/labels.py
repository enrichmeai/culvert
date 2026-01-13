"""FinOps labeling and tagging."""

from typing import Dict, Optional


class FinOpsLabels:
    """Standardized labels for FinOps cost allocation."""

    def __init__(self, system_id: str, environment: str, project: str = "gdw-data-core"):
        """
        Initialize FinOps labels.

        Args:
            system_id: System identifier (e.g., EM, LOA).
            environment: Environment (e.g., DEV, PROD).
            project: Project name (defaults to "gdw-data-core").
        """
        self.system_id = system_id
        self.environment = environment
        self.project = project

    def to_dict(self) -> Dict[str, str]:
        """
        Convert labels to a GCP-compatible dictionary.

        Returns:
            Dictionary of lowercase labels suitable for GCP resources.
        """
        return {
            "system": self.system_id.lower(),
            "environment": self.environment.lower(),
            "project": self.project.lower(),
            "managed_by": "terraform-and-library"
        }

    @staticmethod
    def get_standard_labels(system_id: str, environment: str, run_id: Optional[str] = None) -> Dict[str, str]:
        """
        Utility to get standard label set.

        Args:
            system_id: System identifier.
            environment: Deployment environment.
            run_id: Optional pipeline run identifier.

        Returns:
            Dictionary of standard labels.
        """
        labels = {
            "system": system_id.lower(),
            "environment": environment.lower(),
            "managed_by": "gcp-pipeline-library"
        }
        if run_id:
            labels["run_id"] = run_id.lower()
        return labels

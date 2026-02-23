"""
Pipeline Configuration Module

Defines configuration dataclass and validation for GDW migration pipelines.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """
    Pipeline configuration dataclass.

    Centralizes all pipeline configuration parameters with validation
    and sensible defaults.

    Attributes:
        run_id: Unique identifier for this pipeline execution
        pipeline_name: Descriptive name of the pipeline
        entity_type: Type of entity being processed (e.g., 'applications', 'customers')
        source_file: Path or identifier of the input source
        gcp_project_id: GCP project ID for cloud resources
        bigquery_dataset: BigQuery dataset name for output tables
        additional_config: Dictionary for additional configuration parameters

    Example:
        >>> config = PipelineConfig(
        ...     run_id='run_20231225_001',
        ...     pipeline_name='application2_applications_migration',
        ...     entity_type='applications',
        ...     source_file='gs://bucket/input/applications.csv',
        ...     gcp_project_id='my-gcp-project',
        ...     bigquery_dataset='migration_dataset'
        ... )
        >>> config.validate()
    """

    run_id: str
    pipeline_name: str
    entity_type: str = 'data'
    source_file: str = 'unknown'
    gcp_project_id: Optional[str] = None
    bigquery_dataset: Optional[str] = None
    additional_config: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """
        Validate pipeline configuration.

        Ensures all required fields are present and valid.

        Raises:
            ValueError: If required fields are missing or invalid

        Raises:
            ValueError: If run_id is empty or None
            ValueError: If pipeline_name is empty or None
        """
        if not self.run_id:
            raise ValueError("run_id is required and cannot be empty")

        if not self.pipeline_name:
            raise ValueError("pipeline_name is required and cannot be empty")

        logger.debug(
            f"Configuration validated: run_id={self.run_id}, "
            f"pipeline_name={self.pipeline_name}, entity_type={self.entity_type}"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Provides dict-like access for backward compatibility with code
        expecting a dictionary-based config.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # First check instance attributes
        if hasattr(self, key):
            return getattr(self, key)

        # Then check additional_config dictionary
        return self.additional_config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        return {
            'run_id': self.run_id,
            'pipeline_name': self.pipeline_name,
            'entity_type': self.entity_type,
            'source_file': self.source_file,
            'gcp_project_id': self.gcp_project_id,
            'bigquery_dataset': self.bigquery_dataset,
            **self.additional_config
        }


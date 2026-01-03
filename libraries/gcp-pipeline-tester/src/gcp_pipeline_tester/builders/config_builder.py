"""
Config Builder Module

Fluent builders for test configuration objects.
"""

from typing import Any, Dict, Optional


class PipelineConfigBuilder:
    """
    Fluent builder for PipelineConfig test objects.

    Example:
        >>> config = (PipelineConfigBuilder()
        ...     .with_run_id('test_run_001')
        ...     .with_pipeline_name('test_pipeline')
        ...     .with_gcp_project('my-project')
        ...     .build())
    """

    def __init__(self):
        """Initialize pipeline config builder."""
        self.config_data = {
            'run_id': 'test_run_001',
            'pipeline_name': 'test_pipeline',
            'entity_type': 'test_entity',
            'source_file': 'gs://test-bucket/input.csv',
        }

    def with_run_id(self, run_id: str) -> 'PipelineConfigBuilder':
        """Set run ID."""
        self.config_data['run_id'] = run_id
        return self

    def with_pipeline_name(self, name: str) -> 'PipelineConfigBuilder':
        """Set pipeline name."""
        self.config_data['pipeline_name'] = name
        return self

    def with_entity_type(self, entity_type: str) -> 'PipelineConfigBuilder':
        """Set entity type."""
        self.config_data['entity_type'] = entity_type
        return self

    def with_source_file(self, source_file: str) -> 'PipelineConfigBuilder':
        """Set source file path."""
        self.config_data['source_file'] = source_file
        return self

    def with_gcp_project(self, project_id: str) -> 'PipelineConfigBuilder':
        """Set GCP project ID."""
        self.config_data['gcp_project_id'] = project_id
        return self

    def with_bigquery_dataset(self, dataset: str) -> 'PipelineConfigBuilder':
        """Set BigQuery dataset."""
        self.config_data['bigquery_dataset'] = dataset
        return self

    def build(self) -> 'PipelineConfig':
        """
        Build PipelineConfig object.

        Returns:
            PipelineConfig instance
        """
        from gcp_pipeline_tester.pipelines.base import PipelineConfig
        return PipelineConfig(**self.config_data)

    def build_dict(self) -> Dict[str, Any]:
        """
        Build configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config_data.copy()


class BeamOptionsBuilder:
    """
    Fluent builder for Beam pipeline options.

    Example:
        >>> options = (BeamOptionsBuilder()
        ...     .with_num_workers(2)
        ...     .with_input_pattern('gs://bucket/input.csv')
        ...     .build())
    """

    def __init__(self):
        """Initialize Beam options builder."""
        self.options_list = []

    def with_num_workers(self, num: int) -> 'BeamOptionsBuilder':
        """Set number of workers."""
        self.options_list.append(f'--num_workers={num}')
        return self

    def with_input_pattern(self, pattern: str) -> 'BeamOptionsBuilder':
        """Set input file pattern."""
        self.options_list.append(f'--input_pattern={pattern}')
        return self

    def with_output_table(self, table: str) -> 'BeamOptionsBuilder':
        """Set output BigQuery table."""
        self.options_list.append(f'--output_table={table}')
        return self

    def with_project(self, project: str) -> 'BeamOptionsBuilder':
        """Set GCP project."""
        self.options_list.append(f'--project={project}')
        return self

    def build(self) -> Any:
        """
        Build PipelineOptions object.

        Returns:
            PipelineOptions instance
        """
        from gcp_pipeline_tester.pipelines.base import GDWPipelineOptions
        return GDWPipelineOptions(self.options_list)


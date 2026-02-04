"""
Orchestration Routing Package

Provides router classes and configuration models for dynamic file type routing.

Classes:
    - DAGRouter: Router for file type detection and configuration resolution
    - PipelineConfig: Configuration for a pipeline route
    - FileType: Enumeration of supported file types
    - ProcessingMode: Enumeration of processing modes

Example:
    ```python
    from gcp_pipeline_orchestration.routing import DAGRouter, PipelineConfig, FileType

    router = DAGRouter()

    # Register pipeline configuration
    config = PipelineConfig(
        file_type=FileType.DATA,
        dag_id='daily_pipeline',
        entity_name='customers',
        table_name='stg_customers',
        required_columns=['customer_id', 'name', 'email']
    )
    router.register_pipeline(config)

    # Get configuration for file type
    pipeline_config = router.get_pipeline_config(FileType.DATA)

    # Validate file structure
    is_valid, missing = router.validate_file_structure(
        FileType.DATA,
        ['customer_id', 'name']
    )
    ```
"""

from .router import DAGRouter
from .config import PipelineConfig, FileType, ProcessingMode
from .yaml_selector import YAMLPipelineSelector

__all__ = [
    'DAGRouter',
    'PipelineConfig',
    'FileType',
    'ProcessingMode',
    'YAMLPipelineSelector',
]


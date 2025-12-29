"""
Orchestration Module

Provides DAG creation and routing utilities for Airflow pipelines.

Subpackages:
    - factories: DAG factory and configuration management
    - routing: Pipeline routing and configuration resolution

Classes Exported:
    - DAGFactory: Factory for creating standardized DAGs
    - DAGRouter: Router for dynamic file type routing
    - DAGConfig: Complete DAG configuration
    - DAGValidator: Configuration validator
    - PipelineConfig: Pipeline route configuration
    - FileType: Enumeration of file types
    - ProcessingMode: Enumeration of processing modes

Example:
    ```python
    from gdw_data_core.orchestration import DAGFactory, DAGRouter

    # Create a DAG
    factory = DAGFactory()
    dag = factory.create_dag_from_dict({
        'dag_id': 'my_dag',
        'schedule_interval': '@daily',
    })

    # Route based on file type
    router = DAGRouter()
    config = router.get_pipeline_config(file_type)
    ```
"""

# Import factories
from .factories import (
    DAGFactory,
    DAGConfig,
    DAGValidator,
    DefaultArgs,
    ScheduleConfig,
    RetryPolicy,
    TimeoutConfig,
    TaskConfig,
    ValidationError,
)

# Import routing
from .routing import (
    DAGRouter,
    PipelineConfig,
    FileType,
    ProcessingMode,
)

__all__ = [
    # Factories
    'DAGFactory',
    'DAGConfig',
    'DAGValidator',
    'DefaultArgs',
    'ScheduleConfig',
    'RetryPolicy',
    'TimeoutConfig',
    'TaskConfig',
    'ValidationError',
    # Routing
    'DAGRouter',
    'PipelineConfig',
    'FileType',
    'ProcessingMode',
]


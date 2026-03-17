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
    from gcp_pipeline_orchestration import DAGFactory, DAGRouter

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
from .factories.dag_factory import create_dags

# Import routing
from .routing import (
    DAGRouter,
    PipelineConfig,
    FileType,
    ProcessingMode,
)

# Import operators
from .operators import (
    BaseDataflowOperator,
    BatchDataflowOperator,
    StreamingDataflowOperator,
    SourceType,
    DataflowJobConfig,
)

# Import callbacks
from .callbacks import (
    ErrorType,
    ErrorHandlerConfig,
    publish_to_dlq,
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    quarantine_file,
    on_schema_mismatch,
    on_data_quality_failure,
    create_error_handler,
)

# Import sensors
from .sensors import BasePubSubPullSensor

# Import dependency checker
from .dependency import EntityDependencyChecker

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
    # Operators
    'BaseDataflowOperator',
    'BatchDataflowOperator',
    'StreamingDataflowOperator',
    'SourceType',
    'DataflowJobConfig',
    # Callbacks
    'ErrorType',
    'ErrorHandlerConfig',
    'publish_to_dlq',
    'on_failure_callback',
    'on_validation_failure',
    'on_routing_failure',
    'quarantine_file',
    'on_schema_mismatch',
    'on_data_quality_failure',
    'create_error_handler',
    # Sensors
    'BasePubSubPullSensor',
    # Dependency
    'EntityDependencyChecker',
    # Config-driven DAG factory
    'create_dags',
]


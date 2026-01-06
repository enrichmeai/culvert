"""
Orchestration Factories Package

Provides factory classes and configuration models for dynamic DAG creation.

Classes:
    - DAGFactory: Factory for creating standardized Airflow DAGs
    - DAGConfig: Complete DAG configuration dataclass
    - DAGValidator: Validator for DAG configurations
    - DefaultArgs: Default arguments configuration
    - ScheduleConfig: Schedule configuration
    - RetryPolicy: Retry policy configuration
    - TimeoutConfig: Timeout configuration
    - TaskConfig: Individual task configuration

Exceptions:
    - ValidationError: Configuration validation error

Example:
    ```python
    from gcp_pipeline_builder.orchestration.factories import DAGFactory, DAGConfig

    factory = DAGFactory()

    # Create from configuration object
    config = DAGConfig(dag_id='my_dag')
    dag = factory.create_dag_from_config(config)

    # Create from dictionary
    config_dict = {
        'dag_id': 'my_dag',
        'schedule_interval': '@daily',
        'tags': ['my-tag'],
    }
    dag = factory.create_dag_from_dict(config_dict)
    ```
"""

from .dag_factory import DAGFactory
from .config import (
    DAGConfig,
    TaskConfig,
    DefaultArgs,
    ScheduleConfig,
    RetryPolicy,
    TimeoutConfig,
)
from .validators import DAGValidator, ValidationError

__all__ = [
    'DAGFactory',
    'DAGConfig',
    'TaskConfig',
    'DefaultArgs',
    'ScheduleConfig',
    'RetryPolicy',
    'TimeoutConfig',
    'DAGValidator',
    'ValidationError',
]


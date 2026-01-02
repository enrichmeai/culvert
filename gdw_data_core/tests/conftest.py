"""
Pytest Configuration and Shared Fixtures

Provides common fixtures and configuration for all tests.
"""

import pytest
import sys
from pathlib import Path

# Add the project root to the path so tests can import gdw_data_core
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def _clear_gcp_client_modules():
    """Remove GCP client modules from sys.modules cache to allow proper mocking."""
    modules_to_clear = [
        'gdw_data_core.core.clients',
        'gdw_data_core.core.clients.gcs_client',
        'gdw_data_core.core.clients.pubsub_client',
    ]
    for mod in list(sys.modules.keys()):
        if any(m in mod for m in ['gcs_client', 'pubsub_client']):
            sys.modules.pop(mod, None)
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)


@pytest.fixture(autouse=True, scope='function')
def reset_gcp_modules_before_test():
    """Clear GCP client modules before each test to ensure clean mocking."""
    _clear_gcp_client_modules()
    yield
    _clear_gcp_client_modules()


@pytest.fixture
def cleanup_dag_factory():
    """Fixture to clean up DAGFactory state after each test."""
    yield
    # Cleanup after test
    from gdw_data_core.orchestration.factories import DAGFactory
    factory = DAGFactory()
    factory.reset_created_dag_ids()


@pytest.fixture
def sample_dag_config():
    """Fixture providing a sample DAG configuration."""
    return {
        'dag_id': 'test_dag',
        'schedule_interval': '@daily',
        'start_date': '2023-01-01',
        'default_args': {
            'owner': 'test_team',
            'retries': 3,
            'retry_delay_minutes': 5,
        },
        'tags': ['test', 'example'],
    }


@pytest.fixture
def sample_pipeline_config():
    """Fixture providing a sample pipeline configuration."""
    from gdw_data_core.orchestration.routing import PipelineConfig, FileType

    return PipelineConfig(
        file_type=FileType.DATA,
        dag_id='test_pipeline',
        entity_name='test_entity',
        table_name='stg_test_entity',
        required_columns=['id', 'name', 'timestamp'],
        validation_rules={'id': 'required'},
    )


__all__ = [
    'cleanup_dag_factory',
    'sample_dag_config',
    'sample_pipeline_config',
]

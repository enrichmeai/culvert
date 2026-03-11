"""
Common Fixtures Module

Common test fixtures and sample data for pipeline tests.
"""

import pytest
from typing import Dict, List, Any


@pytest.fixture
def sample_records() -> List[Dict[str, Any]]:
    """
    Fixture providing sample data records for testing.

    Returns a list of realistic test records with various field types
    and values for use in testing data processing logic.

    Returns:
        List of sample record dictionaries

    Example:
        >>> def test_process_records(sample_records):
        ...     assert len(sample_records) > 0
        ...     assert 'id' in sample_records[0]
    """
    return [
        {
            'id': '1',
            'name': 'John Smith',
            'email': 'john.smith@example.com',
            'status': 'active',
            'score': 85
        },
        {
            'id': '2',
            'name': 'Jane Doe',
            'email': 'jane.doe@example.com',
            'status': 'active',
            'score': 92
        },
        {
            'id': '3',
            'name': 'Bob Johnson',
            'email': 'bob.johnson@example.com',
            'status': 'inactive',
            'score': 78
        },
        {
            'id': '4',
            'name': 'Alice Brown',
            'email': 'alice.brown@example.com',
            'status': 'active',
            'score': 95
        },
    ]


@pytest.fixture
def sample_csv_data() -> str:
    """
    Fixture providing sample CSV content for testing.

    Returns:
        CSV formatted string with headers and rows

    Example:
        >>> def test_parse_csv(sample_csv_data):
        ...     lines = sample_csv_data.strip().split('\\n')
        ...     assert lines[0] == 'id,name,email'
    """
    return """id,name,email
1,John Smith,john@example.com
2,Jane Doe,jane@example.com
3,Bob Johnson,bob@example.com
"""


@pytest.fixture
def sample_config_dict() -> Dict[str, Any]:
    """
    Fixture providing sample configuration dictionary.

    Returns:
        Configuration dictionary with typical pipeline settings

    Example:
        >>> def test_with_config(sample_config_dict):
        ...     assert sample_config_dict['pipeline_name'] is not None
    """
    return {
        'run_id': 'test_run_001',
        'pipeline_name': 'test_pipeline',
        'entity_type': 'test_entity',
        'source_file': 'gs://test-bucket/input.csv',
        'gcp_project_id': 'test-project',
        'bigquery_dataset': 'test_dataset',
    }


@pytest.fixture
def sample_pipeline_config():
    """
    Fixture providing sample PipelineConfig instance.

    Returns:
        PipelineConfig object for testing

    Example:
        >>> def test_with_pipeline_config(sample_pipeline_config):
        ...     assert sample_pipeline_config.run_id is not None
    """
    from gcp_pipeline_tester.pipelines.base import PipelineConfig

    return PipelineConfig(
        run_id='test_run_001',
        pipeline_name='test_pipeline',
        entity_type='test_entity',
        source_file='gs://test-bucket/input.csv',
        gcp_project_id='test-project',
        bigquery_dataset='test_dataset',
    )


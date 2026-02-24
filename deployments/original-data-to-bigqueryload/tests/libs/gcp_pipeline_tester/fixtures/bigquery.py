"""
BigQuery Fixtures Module

Test fixtures for BigQuery testing.
"""

import pytest
from unittest.mock import Mock
from typing import Dict, List, Any


@pytest.fixture
def bq_client_mock():
    """
    Fixture providing a mocked BigQuery client.

    Returns:
        Mock BigQuery client with insert_rows_json method

    Example:
        >>> def test_with_bq_mock(bq_client_mock):
        ...     bq_client_mock.insert_rows_json.return_value = []
    """
    mock_client = Mock()
    mock_client.insert_rows_json.return_value = []
    return mock_client


@pytest.fixture
def bq_dataset_mock() -> str:
    """
    Fixture providing a mock BigQuery dataset name.

    Returns:
        str: Mock dataset name

    Example:
        >>> def test_with_dataset(bq_dataset_mock):
        ...     table_id = f"project.{bq_dataset_mock}.table"
    """
    return "test_dataset"


@pytest.fixture
def bq_table_schema() -> List[Dict[str, str]]:
    """
    Fixture providing a sample BigQuery table schema.

    Returns:
        List of schema field definitions

    Example:
        >>> def test_with_schema(bq_table_schema):
        ...     assert len(bq_table_schema) > 0
    """
    return [
        {"name": "id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "email", "type": "STRING", "mode": "NULLABLE"},
        {"name": "score", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]


@pytest.fixture
def bq_test_data() -> List[Dict[str, Any]]:
    """
    Fixture providing sample data for BigQuery testing.

    Returns:
        List of test records to write to BigQuery

    Example:
        >>> def test_write_to_bq(bq_test_data):
        ...     for record in bq_test_data:
        ...         assert 'id' in record
    """
    return [
        {"id": "1", "name": "John", "email": "john@example.com", "score": 85},
        {"id": "2", "name": "Jane", "email": "jane@example.com", "score": 92},
        {"id": "3", "name": "Bob", "email": "bob@example.com", "score": 78},
    ]


"""Unit tests for BigQueryClient."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd

from gdw_data_core.core.clients import BigQueryClient


@pytest.fixture
def bq_client():
    """Create a BigQueryClient with mocked Google client."""
    with patch('google.cloud.bigquery.Client'):
        return BigQueryClient(project='test-project', dataset='test_dataset')


class TestBigQueryClient:
    """Test BigQueryClient class."""

    def test_initialization(self, bq_client):
        """Test client initialization."""
        assert bq_client.project == 'test-project'
        assert bq_client.dataset == 'test_dataset'

    def test_write_to_table_success(self, bq_client):
        """Test writing data to table."""
        test_data = [{'id': 1, 'name': 'test1'}, {'id': 2, 'name': 'test2'}]
        bq_client.client.load_table_from_dataframe = MagicMock(
            return_value=MagicMock(result=MagicMock())
        )
        result = bq_client.write_to_table('test_table', test_data)
        assert result is True

    def test_read_table_success(self, bq_client):
        """Test reading from table."""
        test_df = pd.DataFrame({'id': [1, 2], 'name': ['test1', 'test2']})
        bq_client.client.query = MagicMock(
            return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df))
        )
        result = bq_client.read_table('test_table')
        assert len(result) == 2

    def test_table_exists(self, bq_client):
        """Test checking if table exists."""
        bq_client.client.get_table = MagicMock()
        result = bq_client.table_exists('test_table')
        assert result is True

    def test_query_success(self, bq_client):
        """Test running a query."""
        test_df = pd.DataFrame({'count': [100]})
        bq_client.client.query = MagicMock(
            return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df))
        )
        result = bq_client.query("SELECT COUNT(*) as count FROM test_table")
        assert len(result) == 1


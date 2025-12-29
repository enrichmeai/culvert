import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from gdw_data_core.core.clients import BigQueryClient

@pytest.fixture
def bq_client():
    with patch('google.cloud.bigquery.Client'):
        return BigQueryClient(project='test-project', dataset='test_dataset')

def test_bigquery_client_initialization(bq_client):
    assert bq_client.project == 'test-project'
    assert bq_client.dataset == 'test_dataset'

def test_write_to_table_success(bq_client):
    test_data = [{'id': 1, 'name': 'test1'}, {'id': 2, 'name': 'test2'}]
    bq_client.client.load_table_from_dataframe = MagicMock(return_value=MagicMock(result=MagicMock()))
    result = bq_client.write_to_table('test_table', test_data)
    assert result is True

def test_read_table_success(bq_client):
    test_df = pd.DataFrame({'id': [1, 2], 'name': ['test1', 'test2']})
    bq_client.client.query = MagicMock(return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df)))
    result = bq_client.read_table('test_table')
    assert len(result) == 2

def test_table_exists(bq_client):
    bq_client.client.get_table = MagicMock()
    result = bq_client.table_exists('test_table')
    assert result is True

def test_query_success(bq_client):
    test_df = pd.DataFrame({'count': [100]})
    bq_client.client.query = MagicMock(return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df)))
    result = bq_client.query("SELECT COUNT(*) as count FROM test_table")
    assert len(result) == 1


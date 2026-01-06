"""Unit tests for BigQueryClient.

Tests mirror source: gcp_pipeline_builder/core/clients/bigquery_client.py
Uses late imports to avoid module caching issues.
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch
import pandas as pd


def _reload_bigquery_client():
    """Force reload of bigquery_client module to pick up mocks."""
    for mod in list(sys.modules.keys()):
        if 'bigquery_client' in mod or 'gcp_pipeline_builder.clients' == mod:
            del sys.modules[mod]
    from gcp_pipeline_builder.clients.bigquery_client import BigQueryClient
    return BigQueryClient


class TestBigQueryClientInit:
    """Tests for BigQueryClient initialization."""

    def test_initialization(self):
        """Test client initialization."""
        with patch('gcp_pipeline_builder.clients.bigquery_client.bigquery.Client'):
            BigQueryClient = _reload_bigquery_client()
            client = BigQueryClient(project='test-project', dataset='test_dataset')
            assert client.project == 'test-project'
            assert client.dataset == 'test_dataset'


class TestBigQueryClientWriteTable:
    """Tests for BigQueryClient.write_to_table method."""

    def test_write_to_table_success(self):
        """Test writing data to table."""
        with patch('gcp_pipeline_builder.clients.bigquery_client.bigquery.Client') as mock_bq:
            BigQueryClient = _reload_bigquery_client()
            client = BigQueryClient(project='test-project', dataset='test_dataset')

            test_data = [{'id': 1, 'name': 'test1'}, {'id': 2, 'name': 'test2'}]
            client.client.load_table_from_dataframe = MagicMock(
                return_value=MagicMock(result=MagicMock())
            )
            result = client.write_to_table('test_table', test_data)
            assert result is True


class TestBigQueryClientReadTable:
    """Tests for BigQueryClient.read_table method."""

    def test_read_table_success(self):
        """Test reading from table."""
        with patch('gcp_pipeline_builder.clients.bigquery_client.bigquery.Client') as mock_bq:
            BigQueryClient = _reload_bigquery_client()
            client = BigQueryClient(project='test-project', dataset='test_dataset')

            test_df = pd.DataFrame({'id': [1, 2], 'name': ['test1', 'test2']})
            client.client.query = MagicMock(
                return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df))
            )
            result = client.read_table('test_table')
            assert len(result) == 2


class TestBigQueryClientTableExists:
    """Tests for BigQueryClient.table_exists method."""

    def test_table_exists(self):
        """Test checking if table exists."""
        with patch('gcp_pipeline_builder.clients.bigquery_client.bigquery.Client') as mock_bq:
            BigQueryClient = _reload_bigquery_client()
            client = BigQueryClient(project='test-project', dataset='test_dataset')

            client.client.get_table = MagicMock()
            result = client.table_exists('test_table')
            assert result is True


class TestBigQueryClientQuery:
    """Tests for BigQueryClient.query method."""

    def test_query_success(self):
        """Test running a query."""
        with patch('gcp_pipeline_builder.clients.bigquery_client.bigquery.Client') as mock_bq:
            BigQueryClient = _reload_bigquery_client()
            client = BigQueryClient(project='test-project', dataset='test_dataset')

            test_df = pd.DataFrame({'count': [100]})
            client.client.query = MagicMock(
                return_value=MagicMock(to_dataframe=MagicMock(return_value=test_df))
            )
            result = client.query("SELECT COUNT(*) as count FROM test_table")
            assert len(result) == 1


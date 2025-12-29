"""
Mocks Package

Collection of mock objects for testing without external dependencies.

This package provides mock implementations of external services
like GCS, BigQuery, and Pub/Sub to enable isolated testing.

Exports:
    GCSClientMock: Mock GCS client
    GCSBucketMock: Mock GCS bucket
    BigQueryClientMock: Mock BigQuery client
    BigQueryTableMock: Mock BigQuery table
    PubSubClientMock: Mock Pub/Sub client

Example:
    >>> from gdw_data_core.testing.mocks import GCSClientMock, BigQueryClientMock
    >>>
    >>> gcs_mock = GCSClientMock()
    >>> bq_mock = BigQueryClientMock()
    >>>
    >>> # Use in tests
    >>> gcs_mock.write_file('gs://bucket/file.txt', 'content')
    >>> errors = bq_mock.insert_rows_json('project.dataset.table', [{'id': '1'}])
    >>> assert errors == []
"""

from .gcs_mock import GCSClientMock, GCSBucketMock
from .bigquery_mock import BigQueryClientMock, BigQueryTableMock
from .pubsub_mock import PubSubClientMock

__all__ = [
    'GCSClientMock',
    'GCSBucketMock',
    'BigQueryClientMock',
    'BigQueryTableMock',
    'PubSubClientMock',
]


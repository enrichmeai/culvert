"""
Fixtures Package

Collection of pytest fixtures for GCP pipeline testing.

This package provides reusable test fixtures for common testing scenarios
including sample data, mock objects, and test configurations.

Available Fixtures:
    # Common
    - sample_records: List of sample data records
    - sample_csv_data: Sample CSV formatted content
    - sample_config_dict: Sample configuration dictionary
    - sample_pipeline_config: Sample PipelineConfig object

    # Beam
    - test_pipeline: TestPipeline instance
    - beam_options: PipelineOptions instance
    - sample_beam_record: Sample record for Beam processing

    # GCS
    - gcs_client_mock: Mocked GCS client
    - gcs_bucket_mock: Mock GCS bucket name
    - gcs_test_paths: Sample GCS paths
    - gcs_test_file_content: Sample file content

    # BigQuery
    - bq_client_mock: Mocked BigQuery client
    - bq_dataset_mock: Mock BigQuery dataset name
    - bq_table_schema: Sample BigQuery table schema
    - bq_test_data: Sample BigQuery test data

Example:
    >>> # In conftest.py to use fixtures across tests
    >>> from gcp_pipeline_tester.fixtures import *
    >>>
    >>> # In test file
    >>> def test_with_fixtures(sample_records, test_pipeline):
    ...     assert len(sample_records) > 0
    ...     assert test_pipeline is not None
"""

from .common import (
    sample_records,
    sample_csv_data,
    sample_config_dict,
    sample_pipeline_config,
)
from .beam import (
    test_pipeline,
    beam_options,
    sample_beam_record,
)
from .gcs import (
    gcs_client_mock,
    gcs_bucket_mock,
    gcs_test_paths,
    gcs_test_file_content,
)
from .bigquery import (
    bq_client_mock,
    bq_dataset_mock,
    bq_table_schema,
    bq_test_data,
)

__all__ = [
    # Common fixtures
    'sample_records',
    'sample_csv_data',
    'sample_config_dict',
    'sample_pipeline_config',
    # Beam fixtures
    'test_pipeline',
    'beam_options',
    'sample_beam_record',
    # GCS fixtures
    'gcs_client_mock',
    'gcs_bucket_mock',
    'gcs_test_paths',
    'gcs_test_file_content',
    # BigQuery fixtures
    'bq_client_mock',
    'bq_dataset_mock',
    'bq_table_schema',
    'bq_test_data',
]


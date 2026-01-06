"""
GCP Integration Test Fixtures
==============================

Provides fixtures for testing with GCP services (BigQuery, GCS, Dataflow, Pub/Sub).

Fixtures:
  - gcp_project_id: Test GCP project
  - mock_bq_client: Mocked BigQuery client
  - mock_gcs_client: Mocked GCS client
  - mock_dataflow_client: Mocked Dataflow client
  - mock_pubsub_client: Mocked Pub/Sub client

Usage:
    pytest blueprint/components/tests/integration/ -v -m integration
"""

import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Generator, Dict, Any
from google.cloud import bigquery, storage, pubsub_v1
from google.cloud.dataflow import FlexTemplatesServiceClient


# ============================================================================
# GCP Configuration
# ============================================================================

@pytest.fixture(scope="session")
def gcp_project_id() -> str:
    """Return test GCP project ID."""
    return os.environ.get("GCP_TEST_PROJECT", "loa-test-project")


@pytest.fixture(scope="session")
def gcp_region() -> str:
    """Return test GCP region."""
    return os.environ.get("GCP_TEST_REGION", "us-central1")


@pytest.fixture(scope="session")
def gcp_bucket() -> str:
    """Return test GCS bucket."""
    return os.environ.get("GCP_TEST_BUCKET", "loa-test-bucket")


# ============================================================================
# BigQuery Mocks
# ============================================================================

@pytest.fixture
def mock_bq_client() -> Generator[MagicMock, None, None]:
    """
    Create a mocked BigQuery client.

    Allows testing without actual GCP credentials or resources.
    Simulates common BigQuery operations like query(), get_table(), insert_rows().
    """
    client = MagicMock(spec=bigquery.Client)

    # Mock query execution
    query_job = MagicMock()
    query_job.result.return_value = []
    client.query.return_value = query_job

    # Mock dataset/table operations
    dataset = MagicMock(spec=bigquery.Dataset)
    dataset.dataset_id = "test_dataset"
    client.get_dataset.return_value = dataset

    table = MagicMock(spec=bigquery.Table)
    table.table_id = "test_table"
    table.num_rows = 1000
    client.get_table.return_value = table

    # Mock insert operations
    errors = []
    client.insert_rows.return_value = errors

    yield client


@pytest.fixture
def mock_bq_load_job(mock_bq_client) -> MagicMock:
    """Mock BigQuery load job for GCS to BigQuery operations."""
    load_job = MagicMock()
    load_job.result.return_value = None
    load_job.state = "DONE"
    load_job.output_rows = 1000
    mock_bq_client.load_table_from_uri.return_value = load_job
    return load_job


# ============================================================================
# GCS (Cloud Storage) Mocks
# ============================================================================

@pytest.fixture
def mock_gcs_client() -> Generator[MagicMock, None, None]:
    """
    Create a mocked GCS client.

    Simulates GCS operations like list_blobs(), download_blob(), upload_blob().
    """
    client = MagicMock(spec=storage.Client)

    # Mock bucket operations
    bucket = MagicMock(spec=storage.Bucket)
    bucket.name = "test-bucket"
    client.bucket.return_value = bucket

    # Mock blob operations
    blob = MagicMock(spec=storage.Blob)
    blob.name = "test-file.csv"
    blob.size = 1024
    blob.download_as_bytes.return_value = b"data"
    blob.download_as_string.return_value = "data"
    bucket.blob.return_value = blob

    # Mock list blobs
    bucket.list_blobs.return_value = [blob]

    # Mock existence checks
    blob.exists.return_value = True

    yield client


# ============================================================================
# Dataflow Mocks
# ============================================================================

@pytest.fixture
def mock_dataflow_client() -> Generator[MagicMock, None, None]:
    """
    Create a mocked Dataflow client.

    Simulates Dataflow job operations like launch_template(), get_job().
    """
    client = MagicMock(spec=FlexTemplatesServiceClient)

    # Mock job launch
    response = MagicMock()
    response.job = MagicMock()
    response.job.id = "test-job-12345"
    response.job.state = "JOB_STATE_RUNNING"
    client.launch_flex_template.return_value = response

    # Mock job status
    job = MagicMock()
    job.id = "test-job-12345"
    job.state = "JOB_STATE_DONE"
    job.current_state = "Done"

    yield client


# ============================================================================
# Pub/Sub Mocks
# ============================================================================

@pytest.fixture
def mock_pubsub_publisher() -> Generator[MagicMock, None, None]:
    """
    Create a mocked Pub/Sub publisher client.

    Simulates publishing messages to Pub/Sub topics.
    """
    publisher = MagicMock(spec=pubsub_v1.PublisherClient)

    # Mock publish
    future = MagicMock()
    future.result.return_value = "message-id-12345"
    publisher.publish.return_value = future

    yield publisher


@pytest.fixture
def mock_pubsub_subscriber() -> Generator[MagicMock, None, None]:
    """
    Create a mocked Pub/Sub subscriber client.

    Simulates subscribing to Pub/Sub topics.
    """
    subscriber = MagicMock(spec=pubsub_v1.SubscriberClient)

    # Mock subscribe
    streaming_pull_future = MagicMock()
    streaming_pull_future.result.return_value = None
    subscriber.subscribe.return_value = streaming_pull_future

    yield subscriber


# ============================================================================
# Airflow Mocks
# ============================================================================

@pytest.fixture
def mock_airflow_task_context() -> Dict[str, Any]:
    """
    Create a mock Airflow task context.

    Used for testing task functions that require Airflow context.
    """
    from datetime import datetime, timedelta

    return {
        "run_id": "test_run_1",
        "task_id": "test_task",
        "dag_id": "test_dag",
        "execution_date": datetime(2025, 1, 1, 12, 0, 0),
        "data_interval_start": datetime(2025, 1, 1, 0, 0, 0),
        "data_interval_end": datetime(2025, 1, 2, 0, 0, 0),
        "ts_nodash": "20250101T120000",
        "ti": MagicMock(),  # Task instance
    }


# ============================================================================
# Environment Configuration
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_gcp_test_env():
    """Set up GCP test environment variables."""
    os.environ.setdefault("GCP_TEST_PROJECT", "loa-test-project")
    os.environ.setdefault("GCP_TEST_REGION", "us-central1")
    os.environ.setdefault("GCP_TEST_BUCKET", "loa-test-bucket")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "")




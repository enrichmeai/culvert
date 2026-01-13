import pytest
from unittest.mock import MagicMock
from gcp_pipeline_core.finops.tracker import (
    BigQueryCostTracker, 
    BQ_COST_PER_BYTE,
    CloudStorageCostTracker,
    PubSubCostTracker
)

def test_estimate_query_cost():
    # Mock BigQuery QueryJob
    mock_job = MagicMock()
    mock_job.total_bytes_billed = 1024**4  # 1 TiB
    mock_job.slot_millis = 1000
    mock_job.labels = {"run_id": "test-run"}
    
    metrics = BigQueryCostTracker.estimate_query_cost(mock_job)
    
    assert metrics.run_id == "test-run"
    assert metrics.billed_bytes_scanned == 1024**4
    assert metrics.estimated_cost_usd == pytest.approx(6.25)
    assert metrics.slot_millis == 1000

def test_estimate_query_cost_no_bytes():
    mock_job = MagicMock()
    mock_job.total_bytes_billed = None
    mock_job.labels = {"run_id": "test-run"}
    
    metrics = BigQueryCostTracker.estimate_query_cost(mock_job)
    
    assert metrics.estimated_cost_usd == 0.0
    assert metrics.billed_bytes_scanned == 0

def test_estimate_load_cost():
    mock_job = MagicMock()
    mock_job.output_bytes = 5000
    mock_job.labels = {"run_id": "load-run"}
    
    metrics = BigQueryCostTracker.estimate_load_cost(mock_job)
    
    assert metrics.billed_bytes_written == 5000
    assert metrics.run_id == "load-run"

def test_estimate_gcs_upload_cost():
    mock_blob = MagicMock()
    mock_blob.size = 1024 * 1024  # 1 MiB
    
    metrics = CloudStorageCostTracker.estimate_upload_cost(mock_blob, run_id="gcs-run")
    
    assert metrics.run_id == "gcs-run"
    assert metrics.billed_bytes_written == 1024 * 1024
    assert metrics.estimated_cost_usd > 0

def test_estimate_gcs_storage_cost():
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.size = 1024**3  # 1 GiB
    mock_bucket.list_blobs.return_value = [mock_blob]
    
    metrics = CloudStorageCostTracker.estimate_storage_cost(mock_bucket, run_id="storage-run")
    
    assert metrics.run_id == "storage-run"
    assert metrics.billed_bytes_stored == 1024**3
    assert metrics.estimated_cost_usd == pytest.approx(0.02)

def test_estimate_pubsub_publish_cost():
    metrics = PubSubCostTracker.estimate_publish_cost(500, run_id="pubsub-run")
    
    assert metrics.run_id == "pubsub-run"
    assert metrics.billed_bytes_written == 1024  # Min 1KB
    assert metrics.billed_messages_count == 1
    assert metrics.estimated_cost_usd > 0

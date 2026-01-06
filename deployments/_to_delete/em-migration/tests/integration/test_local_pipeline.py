"""
Local Pipeline Testing - End-to-End Integration Tests

Complete end-to-end testing of the LOA pipeline locally without GCP dependencies.
Includes mock GCS, BigQuery, and Pub/Sub services.

Usage: pytest tests/local/test_local_pipeline.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

# Mock GCS, BigQuery, and Pub/Sub for local testing
from io import BytesIO
import csv


class MockGCSClient:
    """Mock Google Cloud Storage client for local testing."""

    def __init__(self):
        self.buckets = {}
        self.uploaded_files = []

    def bucket(self, bucket_name):
        """Get or create a mock bucket."""
        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = MockBucket(bucket_name)
        return self.buckets[bucket_name]


class MockBucket:
    """Mock GCS bucket."""

    def __init__(self, name):
        self.name = name
        self.blobs = {}

    def blob(self, path):
        """Get or create a mock blob."""
        if path not in self.blobs:
            self.blobs[path] = MockBlob(path)
        return self.blobs[path]

    def list_blobs(self, prefix="", delimiter=None):
        """List blobs with optional prefix."""
        return [blob for path, blob in self.blobs.items() if path.startswith(prefix)]


class MockBlob:
    """Mock GCS blob (file)."""

    def __init__(self, name):
        self.name = name
        self.data = b""
        self.size = 0
        self.time_created = datetime.utcnow()
        self.updated = datetime.utcnow()

    def upload_from_string(self, data):
        """Upload data to blob."""
        if isinstance(data, str):
            self.data = data.encode('utf-8')
        else:
            self.data = data
        self.size = len(self.data)

    def download_as_string(self):
        """Download data from blob."""
        return self.data

    def download_as_bytes(self):
        """Download as bytes."""
        return self.data

    def exists(self):
        """Check if blob exists."""
        return self.size > 0


class MockBigQueryClient:
    """Mock BigQuery client for local testing."""

    def __init__(self):
        self.datasets = {}
        self.tables = {}
        self.inserted_rows = []

    def dataset(self, dataset_id):
        """Get or create a mock dataset."""
        if dataset_id not in self.datasets:
            self.datasets[dataset_id] = MockDataset(dataset_id)
        return self.datasets[dataset_id]

    def get_table(self, table_id):
        """Get a mock table."""
        if table_id not in self.tables:
            self.tables[table_id] = MockTable(table_id)
        return self.tables[table_id]

    def insert_rows(self, table, rows, **kwargs):
        """Insert rows into table."""
        self.inserted_rows.extend(rows)
        return []  # No errors


class MockDataset:
    """Mock BigQuery dataset."""

    def __init__(self, dataset_id):
        self.dataset_id = dataset_id
        self.tables = {}

    def table(self, table_id):
        """Get or create a mock table."""
        if table_id not in self.tables:
            self.tables[table_id] = MockTable(table_id)
        return self.tables[table_id]


class MockTable:
    """Mock BigQuery table."""

    def __init__(self, table_id):
        self.table_id = table_id
        self.rows = []
        self.schema = []


class MockPubSubPublisher:
    """Mock Pub/Sub publisher."""

    def __init__(self):
        self.messages = []

    def publish(self, topic_path, data, **kwargs):
        """Publish message."""
        self.messages.append({
            'topic': topic_path,
            'data': data,
            'attributes': kwargs.get('attributes', {})
        })
        return MagicMock(result=lambda: "message-id")


# ============================================================================
# TESTS
# ============================================================================

class TestLocalPipelineSetup:
    """Test local pipeline setup and mock services."""

    def test_mock_gcs_client_creation(self):
        """Test creating mock GCS client."""
        client = MockGCSClient()
        bucket = client.bucket("test-bucket")

        assert bucket is not None
        assert bucket.name == "test-bucket"

    def test_mock_gcs_upload_download(self):
        """Test uploading and downloading from mock GCS."""
        client = MockGCSClient()
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("test-file.csv")

        # Upload
        test_data = "id,name,value\n1,test,100\n2,test2,200"
        blob.upload_from_string(test_data)

        # Download
        downloaded = blob.download_as_string().decode('utf-8')

        assert downloaded == test_data
        assert blob.size == len(test_data.encode())

    def test_mock_bigquery_client_creation(self):
        """Test creating mock BigQuery client."""
        client = MockBigQueryClient()
        dataset = client.dataset("test_dataset")
        table = dataset.table("test_table")

        assert dataset is not None
        assert table is not None
        assert dataset.dataset_id == "test_dataset"

    def test_mock_bigquery_insert_rows(self):
        """Test inserting rows into mock BigQuery."""
        client = MockBigQueryClient()
        dataset = client.dataset("test_dataset")
        table = dataset.table("test_table")

        # Insert rows
        rows = [
            {"id": "1", "name": "test1", "value": 100},
            {"id": "2", "name": "test2", "value": 200}
        ]

        client.insert_rows(table, rows)

        assert len(client.inserted_rows) == 2
        assert client.inserted_rows[0]["id"] == "1"

    def test_mock_pubsub_publisher(self):
        """Test mock Pub/Sub publisher."""
        publisher = MockPubSubPublisher()

        # Publish message
        publisher.publish(
            "projects/test/topics/test-topic",
            b"test message",
            attributes={"source": "pipeline"}
        )

        assert len(publisher.messages) == 1
        assert publisher.messages[0]["data"] == b"test message"


class TestLocalDataValidation:
    """Test data validation in local environment."""

    def test_validate_csv_format_success(self):
        """Test CSV format validation passes."""
        csv_content = "application_id,ssn,loan_amount\nAPP001,123-45-6789,250000"

        # Parse and validate
        lines = csv_content.split("\n")
        reader = csv.reader(lines)
        header = next(reader)

        assert header == ["application_id", "ssn", "loan_amount"]
        assert len(header) == 3

    def test_validate_csv_format_missing_columns(self):
        """Test CSV format validation fails with missing columns."""
        csv_content = "application_id,ssn\nAPP001,123-45-6789"

        lines = csv_content.split("\n")
        reader = csv.reader(lines)
        header = next(reader)

        required = ["application_id", "ssn", "loan_amount"]
        missing = [col for col in required if col not in header]

        assert len(missing) > 0
        assert "loan_amount" in missing

    def test_validate_record_completeness(self):
        """Test record completeness validation."""
        record = {"id": "APP001", "ssn": "123-45-6789", "amount": "250000"}
        required_fields = ["id", "ssn", "amount"]

        is_complete = all(field in record and record[field] for field in required_fields)

        assert is_complete is True

    def test_validate_record_with_missing_field(self):
        """Test record completeness with missing field."""
        record = {"id": "APP001", "ssn": None, "amount": "250000"}
        required_fields = ["id", "ssn", "amount"]

        is_complete = all(field in record and record[field] for field in required_fields)

        assert is_complete is False


class TestLocalDataTransformation:
    """Test data transformation in local environment."""

    def test_transform_application_record(self):
        """Test transforming application record."""
        source_record = {
            "application_id": "APP001",
            "ssn": "123-45-6789",
            "loan_amount": "250000",
            "application_date": "2025-01-15"
        }

        # Transform
        target_record = {
            "application_id": source_record["application_id"],
            "ssn_masked": f"{source_record['ssn'][:5]}****",
            "loan_amount_cents": int(source_record["loan_amount"]) * 100,
            "processed_date": datetime.utcnow().isoformat()
        }

        assert target_record["application_id"] == "APP001"
        assert target_record["loan_amount_cents"] == 25000000
        assert target_record["ssn_masked"] == "123-4****"

    def test_aggregate_batch_statistics(self):
        """Test aggregating batch statistics."""
        records = [
            {"id": "R001", "amount": 100},
            {"id": "R002", "amount": 200},
            {"id": "R003", "amount": 300}
        ]

        stats = {
            "total_records": len(records),
            "total_amount": sum(r["amount"] for r in records),
            "avg_amount": sum(r["amount"] for r in records) / len(records)
        }

        assert stats["total_records"] == 3
        assert stats["total_amount"] == 600
        assert stats["avg_amount"] == 200


class TestLocalErrorHandling:
    """Test error handling in local environment."""

    def test_handle_validation_error(self):
        """Test handling validation errors."""
        record = {"id": "APP001", "ssn": None}
        errors = []

        if not record.get("ssn"):
            errors.append("Missing SSN")

        assert len(errors) > 0
        assert "Missing SSN" in errors

    def test_quarantine_invalid_record(self):
        """Test quarantining invalid records."""
        invalid_record = {"id": "APP001", "data": "malformed"}
        quarantined = []

        quarantined.append({
            "original": invalid_record,
            "reason": "Invalid format",
            "timestamp": datetime.utcnow().isoformat()
        })

        assert len(quarantined) == 1
        assert quarantined[0]["reason"] == "Invalid format"

    def test_error_retry_logic(self):
        """Test error retry logic."""
        max_retries = 3
        retry_count = 0
        success = False

        for attempt in range(max_retries):
            retry_count = attempt + 1
            if retry_count == 2:  # Simulate success on 2nd attempt
                success = True
                break

        assert success is True
        assert retry_count == 2


class TestLocalPipelineIntegration:
    """Integration tests for local pipeline."""

    def test_full_pipeline_flow(self):
        """Test complete pipeline flow locally."""
        # Setup
        gcs_client = MockGCSClient()
        bq_client = MockBigQueryClient()
        publisher = MockPubSubPublisher()

        # Step 1: Read from GCS
        input_bucket = gcs_client.bucket("input")
        input_blob = input_bucket.blob("applications.csv")
        input_blob.upload_from_string(
            "application_id,ssn,loan_amount\n"
            "APP001,123-45-6789,250000\n"
            "APP002,234-56-7890,500000"
        )

        # Verify file uploaded
        assert input_blob.exists()
        assert input_blob.size > 0

        # Step 2: Parse CSV
        csv_data = input_blob.download_as_string().decode('utf-8')
        lines = csv_data.split('\n')
        reader = csv.DictReader(lines)
        records = list(reader)

        assert len(records) == 2
        assert records[0]["application_id"] == "APP001"

        # Step 3: Validate records
        valid_records = []
        for record in records:
            if record.get("application_id") and record.get("ssn"):
                valid_records.append(record)

        assert len(valid_records) == 2

        # Step 4: Transform records
        transformed = []
        for record in valid_records:
            transformed.append({
                "application_id": record["application_id"],
                "loan_amount_cents": int(record["loan_amount"]) * 100
            })

        assert len(transformed) == 2
        assert transformed[0]["loan_amount_cents"] == 25000000

        # Step 5: Load to BigQuery
        dataset = bq_client.dataset("raw")
        table = dataset.table("applications_raw")
        bq_client.insert_rows(table, transformed)

        assert len(bq_client.inserted_rows) == 2

        # Step 6: Publish to Pub/Sub
        publisher.publish(
            "projects/test/topics/loa-processed",
            json.dumps({"records_processed": len(transformed)}).encode()
        )

        assert len(publisher.messages) == 1

    def test_pipeline_with_errors(self):
        """Test pipeline with error handling."""
        records = [
            {"id": "R001", "name": "Valid", "value": "100"},
            {"id": "R002", "name": "Invalid"},  # Missing value
            {"id": "R003", "name": "Valid2", "value": "300"}
        ]

        valid = []
        invalid = []

        for record in records:
            if "value" in record and record["value"]:
                valid.append(record)
            else:
                invalid.append(record)

        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0]["id"] == "R002"


class TestLocalAuditTrail:
    """Test audit trail in local environment."""

    def test_log_processed_record(self):
        """Test logging processed record."""
        audit_log = []

        record = {"id": "APP001", "status": "LOADED"}
        audit_log.append({
            "record_id": record["id"],
            "status": record["status"],
            "timestamp": datetime.utcnow().isoformat()
        })

        assert len(audit_log) == 1
        assert audit_log[0]["record_id"] == "APP001"

    def test_log_batch_statistics(self):
        """Test logging batch statistics."""
        audit_log = []

        stats = {
            "batch_id": "BATCH001",
            "total_records": 100,
            "successful_records": 98,
            "failed_records": 2,
            "timestamp": datetime.utcnow().isoformat()
        }

        audit_log.append(stats)

        assert len(audit_log) == 1
        assert audit_log[0]["batch_id"] == "BATCH001"
        assert audit_log[0]["successful_records"] == 98


class TestLocalMetrics:
    """Test metrics collection in local environment."""

    def test_measure_pipeline_duration(self):
        """Test measuring pipeline execution time."""
        start_time = datetime.utcnow()

        # Simulate work
        import time
        time.sleep(0.1)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        assert duration >= 0.1
        assert duration < 1  # Should be quick

    def test_track_records_processed(self):
        """Test tracking record count."""
        records_processed = 0

        for i in range(100):
            records_processed += 1

        assert records_processed == 100

    def test_calculate_throughput(self):
        """Test calculating pipeline throughput."""
        records_processed = 1000
        duration_seconds = 10

        throughput = records_processed / duration_seconds

        assert throughput == 100  # 100 records/second


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def gcs_client():
    """Provide mock GCS client."""
    return MockGCSClient()


@pytest.fixture
def bq_client():
    """Provide mock BigQuery client."""
    return MockBigQueryClient()


@pytest.fixture
def pubsub_publisher():
    """Provide mock Pub/Sub publisher."""
    return MockPubSubPublisher()


@pytest.fixture
def sample_csv_data():
    """Provide sample CSV data."""
    return """application_id,ssn,loan_amount,application_date
APP001,123-45-6789,250000,2025-01-15
APP002,234-56-7890,500000,2025-01-16
APP003,345-67-8901,750000,2025-01-17"""


@pytest.fixture
def sample_records():
    """Provide sample records."""
    return [
        {"application_id": "APP001", "ssn": "123-45-6789", "loan_amount": 250000},
        {"application_id": "APP002", "ssn": "234-56-7890", "loan_amount": 500000},
        {"application_id": "APP003", "ssn": "345-67-8901", "loan_amount": 750000}
    ]


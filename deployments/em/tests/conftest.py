"""
PyTest Configuration and Fixtures for EM Blueprint Tests
==========================================================

Provides centralized fixtures for:
- EM entity test data (customers, accounts, decision)
- Sample CSV files with HDR/TRL records
- BigQuery client mocking for unit tests
- Sample Airflow DAG instantiation for DAG testing

All fixtures include proper cleanup and documentation.

Usage:
    pytest tests/ -v
    pytest tests/unit/ -v
    pytest tests/integration/ -v

Scope:
    - session: Single instance for entire test session
    - function: New instance for each test function
"""

import csv
import os
import shutil
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Generator
from unittest.mock import MagicMock

import pytest

try:
    from faker import Faker as FakerClass
except ImportError:
    FakerClass = None  # type: ignore # Will be skipped if faker not installed


# ============================================================================
# EM CUSTOMER FIXTURES
# ============================================================================

@pytest.fixture
def em_customer_record():
    """Valid EM customer record."""
    return {
        "customer_id": "C001",
        "first_name": "John",
        "last_name": "Doe",
        "ssn": "123-45-6789",
        "dob": "1980-01-15",
        "status": "A",
        "created_date": "2020-01-01",
    }


@pytest.fixture
def em_customer_records():
    """Multiple EM customer records for batch testing."""
    return [
        {
            "customer_id": "C001",
            "first_name": "John",
            "last_name": "Doe",
            "ssn": "123-45-6789",
            "dob": "1980-01-15",
            "status": "A",
            "created_date": "2020-01-01",
        },
        {
            "customer_id": "C002",
            "first_name": "Jane",
            "last_name": "Smith",
            "ssn": "987-65-4321",
            "dob": "1985-06-20",
            "status": "A",
            "created_date": "2021-03-15",
        },
        {
            "customer_id": "C003",
            "first_name": "Bob",
            "last_name": "Johnson",
            "ssn": "555-55-5555",
            "dob": "1975-12-01",
            "status": "I",
            "created_date": "2019-06-01",
        },
    ]


# ============================================================================
# EM ACCOUNT FIXTURES
# ============================================================================

@pytest.fixture
def em_account_record():
    """Valid EM account record."""
    return {
        "account_id": "A001",
        "customer_id": "C001",
        "account_type": "CHECKING",
        "balance": "10000.50",
        "status": "A",
        "open_date": "2020-06-01",
    }


@pytest.fixture
def em_account_records():
    """Multiple EM account records for batch testing."""
    return [
        {
            "account_id": "A001",
            "customer_id": "C001",
            "account_type": "CHECKING",
            "balance": "10000.50",
            "status": "A",
            "open_date": "2020-06-01",
        },
        {
            "account_id": "A002",
            "customer_id": "C001",
            "account_type": "SAVINGS",
            "balance": "25000.00",
            "status": "A",
            "open_date": "2020-06-15",
        },
        {
            "account_id": "A003",
            "customer_id": "C002",
            "account_type": "MONEY_MARKET",
            "balance": "50000.00",
            "status": "A",
            "open_date": "2021-04-01",
        },
    ]


# ============================================================================
# EM DECISION FIXTURES
# ============================================================================

@pytest.fixture
def em_decision_record():
    """Valid EM decision record."""
    return {
        "decision_id": "D001",
        "customer_id": "C001",
        "application_id": "APP001",
        "decision_code": "APPROVE",
        "decision_date": "2026-01-01T10:30:00",
        "score": "720",
        "reason_codes": "R01|R02",
    }


@pytest.fixture
def em_decision_records():
    """Multiple EM decision records for batch testing."""
    return [
        {
            "decision_id": "D001",
            "customer_id": "C001",
            "application_id": "APP001",
            "decision_code": "APPROVE",
            "decision_date": "2026-01-01T10:30:00",
            "score": "720",
            "reason_codes": "R01|R02",
        },
        {
            "decision_id": "D002",
            "customer_id": "C002",
            "application_id": "APP002",
            "decision_code": "DECLINE",
            "decision_date": "2026-01-01T11:00:00",
            "score": "580",
            "reason_codes": "R03|R04|R05",
        },
        {
            "decision_id": "D003",
            "customer_id": "C003",
            "application_id": "APP003",
            "decision_code": "REVIEW",
            "decision_date": "2026-01-01T11:30:00",
            "score": "650",
            "reason_codes": "R06",
        },
    ]


# ============================================================================
# EM FILE FIXTURES (with HDR/TRL)
# ============================================================================

@pytest.fixture
def em_customers_file_lines():
    """Sample EM customers file with HDR/TRL."""
    return [
        "HDR|EM|customers|20260101",
        "customer_id,first_name,last_name,ssn,dob,status,created_date",
        "C001,John,Doe,123-45-6789,1980-01-15,A,2020-01-01",
        "C002,Jane,Smith,987-65-4321,1985-06-20,A,2021-03-15",
        "C003,Bob,Johnson,555-55-5555,1975-12-01,I,2019-06-01",
        "TRL|RecordCount=3|Checksum=abc123",
    ]


@pytest.fixture
def em_accounts_file_lines():
    """Sample EM accounts file with HDR/TRL."""
    return [
        "HDR|EM|accounts|20260101",
        "account_id,customer_id,account_type,balance,status,open_date",
        "A001,C001,CHECKING,10000.50,A,2020-06-01",
        "A002,C001,SAVINGS,25000.00,A,2020-06-15",
        "A003,C002,MONEY_MARKET,50000.00,A,2021-04-01",
        "TRL|RecordCount=3|Checksum=def456",
    ]


@pytest.fixture
def em_decision_file_lines():
    """Sample EM decision file with HDR/TRL."""
    return [
        "HDR|EM|decision|20260101",
        "decision_id,customer_id,application_id,decision_code,decision_date,score,reason_codes",
        "D001,C001,APP001,APPROVE,2026-01-01T10:30:00,720,R01|R02",
        "D002,C002,APP002,DECLINE,2026-01-01T11:00:00,580,R03|R04|R05",
        "D003,C003,APP003,REVIEW,2026-01-01T11:30:00,650,R06",
        "TRL|RecordCount=3|Checksum=ghi789",
    ]


# ============================================================================
# COMMON FIXTURES
# ============================================================================

@pytest.fixture
def em_extract_date():
    """Sample extract date."""
    return date(2026, 1, 1)


@pytest.fixture
def em_run_id():
    """Sample run ID."""
    return "em_customers_20260101_103000"


@pytest.fixture(scope="function")
def temp_output_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp(prefix="em_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_csv_file(temp_output_dir, em_customers_file_lines) -> Generator[str, None, None]:
    """Create a temporary CSV file with EM customer data."""
    file_path = os.path.join(temp_output_dir, "em_customers_20260101.csv")
    with open(file_path, 'w', newline='') as f:
        for line in em_customers_file_lines:
            f.write(line + '\n')
    yield file_path


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client for unit tests."""
    client = MagicMock()
    client.query.return_value.result.return_value = []
    client.insert_rows_json.return_value = []
    return client


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client for unit tests."""
    client = MagicMock()
    client.list_blobs.return_value = []
    return client


@pytest.fixture
def mock_pubsub_client():
    """Mock Pub/Sub client for unit tests."""
    client = MagicMock()
    client.pull.return_value.received_messages = []
    return client


@pytest.fixture(scope="function")
def mock_bigquery() -> MagicMock:
    """
    Create a mock BigQuery client for unit testing.

    Returns a fully mocked BigQuery client with common methods:
    - load_table_from_file: Returns a mock LoadJob
    - get_table: Returns table metadata
    - insert_rows_json: Returns insert results
    - query: Returns query results
    """
    mock_client = MagicMock()

    # Mock load_table_from_file method
    mock_load_job = MagicMock()
    mock_load_job.job_id = 'test_load_job_20260101_001'
    mock_load_job.state = 'DONE'
    mock_load_job.result.return_value = MagicMock()
    mock_client.load_table_from_file.return_value = mock_load_job

    # Mock get_table method
    mock_table = MagicMock()
    mock_table.num_rows = 1000
    mock_table.num_bytes = 512000
    mock_table.schema = [
        MagicMock(name='customer_id', field_type='STRING'),
        MagicMock(name='first_name', field_type='STRING'),
        MagicMock(name='status', field_type='STRING'),
    ]
    mock_client.get_table.return_value = mock_table

    # Mock insert_rows_json method
    mock_client.insert_rows_json.return_value = []  # No errors

    # Mock query method
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_client.query.return_value = mock_query_job

    # Mock list_tables method
    mock_client.list_tables.return_value = []

    return mock_client


# ============================================================================
# SAMPLE AIRFLOW DAG FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def sample_dag():
    """
    Create a sample EM Airflow DAG for testing DAG structure and tasks.
    """
    try:
        from em.orchestration.airflow.dags.em_daily_load_dag import dag
        return dag
    except ImportError as e:
        pytest.skip(f"EM DAG module not available: {str(e)}")


# ============================================================================
# FIXTURE UTILITIES AND HELPERS
# ============================================================================

@pytest.fixture(scope="session")
def faker_instance():
    """
    Provide a Faker instance with fixed seed for reproducibility.
    """
    if FakerClass is None:
        pytest.skip("Faker package not installed")

    faker = FakerClass()
    FakerClass.seed(42)
    return faker


@pytest.fixture(scope="function")
def isolated_filesystem(tmp_path) -> Path:
    """
    Provide an isolated temporary filesystem for tests.
    """
    return tmp_path


# ============================================================================
# PYTEST CONFIGURATION HOOKS
# ============================================================================

def pytest_configure(config):
    """
    Configure pytest with custom markers and settings.
    """
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_gcp: mark test as requiring GCP credentials"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers based on test paths.
    """
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


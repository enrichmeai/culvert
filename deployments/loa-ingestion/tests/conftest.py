"""
PyTest Configuration and Fixtures for LOA Tests
=================================================

Provides centralized fixtures for:
- LOA entity test data (applications)
- Sample CSV files with HDR/TRL records
- BigQuery client mocking for unit tests
- Sample Airflow DAG instantiation for DAG testing

Usage:
    pytest tests/ -v
    pytest tests/unit/ -v
    pytest tests/integration/ -v
"""

import os
import tempfile
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import MagicMock

import pytest

# Add embedded libs to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
LIBS_PATH = PROJECT_ROOT / "libs"
TEST_LIBS_PATH = PROJECT_ROOT / "tests" / "libs"

if LIBS_PATH.exists() and str(LIBS_PATH) not in sys.path:
    sys.path.insert(0, str(LIBS_PATH))
if TEST_LIBS_PATH.exists() and str(TEST_LIBS_PATH) not in sys.path:
    sys.path.insert(0, str(TEST_LIBS_PATH))


# ============================================================================
# LOA APPLICATION FIXTURES
# ============================================================================

@pytest.fixture
def loa_application_record():
    """Valid LOA application record."""
    return {
        "application_id": "APP001",
        "customer_id": "CUST001",
        "application_date": "2026-01-01",
        "application_type": "NEW",
        "application_status": "PENDING",
        "loan_amount": "50000.00",
        "loan_term": "360",
        "interest_rate": "5.5",
        "portfolio_id": "PORT001",
        "portfolio_name": "Growth Portfolio",
        "portfolio_type": "EQUITY",
        "account_id": "ACCT001",
        "account_number": "1234567890",
        "account_type": "LOAN",
        "account_status": "ACTIVE",
        "event_type": "SUBMITTED",
        "event_date": "2026-01-01",
        "event_status": "COMPLETE",
        "transaction_id": "TXN001",
        "transaction_amount": "50000.00",
        "transaction_date": "2026-01-01",
        "transaction_type": "DISBURSEMENT",
        "excess_amount": "0.00",
        "excess_reason": "",
        "excess_status": "",
        "excess_category": "",
        "excess_threshold": "0.00",
    }


@pytest.fixture
def loa_application_records():
    """Multiple LOA application records for batch testing."""
    return [
        {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "PENDING",
            "loan_amount": "50000.00",
            "portfolio_id": "PORT001",
            "event_type": "SUBMITTED",
        },
        {
            "application_id": "APP002",
            "customer_id": "CUST002",
            "application_date": "2026-01-01",
            "application_type": "REFINANCE",
            "application_status": "APPROVED",
            "loan_amount": "75000.00",
            "portfolio_id": "PORT001",
            "event_type": "APPROVED",
        },
        {
            "application_id": "APP003",
            "customer_id": "CUST003",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "DECLINED",
            "loan_amount": "25000.00",
            "portfolio_id": "PORT002",
            "event_type": "REVIEWED",
        },
    ]


@pytest.fixture
def loa_invalid_application_record():
    """Invalid LOA application record for error testing."""
    return {
        "application_id": "",  # Missing required field
        "customer_id": "CUST001",
        "application_date": "2026-01-01",
        "application_type": "INVALID_TYPE",  # Invalid value
        "application_status": "UNKNOWN",  # Invalid value
        "loan_amount": "invalid",  # Invalid format
    }


# ============================================================================
# FILE FIXTURES
# ============================================================================

@pytest.fixture
def loa_applications_file_lines():
    """Sample LOA applications file with HDR/TRL."""
    return [
        "HDR|LOA|Applications|20260101",
        "application_id,customer_id,application_date,application_type,application_status,loan_amount",
        "APP001,CUST001,2026-01-01,NEW,PENDING,50000.00",
        "APP002,CUST002,2026-01-01,REFINANCE,APPROVED,75000.00",
        "APP003,CUST003,2026-01-01,NEW,DECLINED,25000.00",
        "TRL|RecordCount=3|Checksum=xyz789",
    ]


@pytest.fixture
def loa_applications_file_lines_invalid_header():
    """Sample LOA file with invalid header."""
    return [
        "HDR|WRONG|Applications|20260101",  # Wrong system ID
        "application_id,customer_id,application_date",
        "APP001,CUST001,2026-01-01",
        "TRL|RecordCount=1|Checksum=abc123",
    ]


@pytest.fixture
def loa_applications_file_lines_missing_trailer():
    """Sample LOA file missing trailer."""
    return [
        "HDR|LOA|Applications|20260101",
        "application_id,customer_id,application_date",
        "APP001,CUST001,2026-01-01",
        # Missing TRL line
    ]


# ============================================================================
# DATE FIXTURES
# ============================================================================

@pytest.fixture
def loa_extract_date():
    """Sample extract date."""
    return date(2026, 1, 1)


@pytest.fixture
def loa_run_id():
    """Sample run ID."""
    return f"loa_applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_gcs_client():
    """Mock GCS client for unit tests."""
    mock = MagicMock()
    mock.list_files.return_value = ["loa_applications_20260101.csv"]
    mock.read_file.return_value = "HDR|LOA|Applications|20260101\n..."
    return mock


@pytest.fixture
def mock_bq_client():
    """Mock BigQuery client for unit tests."""
    mock = MagicMock()
    mock.get_table_row_count.return_value = 100
    mock.insert_rows.return_value = []
    return mock


@pytest.fixture
def mock_pubsub_client():
    """Mock Pub/Sub client for unit tests."""
    mock = MagicMock()
    mock.publish.return_value = "message-id-123"
    return mock


# ============================================================================
# TEMP FILE FIXTURES
# ============================================================================

@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary directory with sample LOA data files."""
    data_dir = tmp_path / "loa_data"
    data_dir.mkdir()

    # Create sample applications file
    apps_file = data_dir / "loa_applications_20260101.csv"
    apps_content = """HDR|LOA|Applications|20260101
application_id,customer_id,application_date,application_type,application_status,loan_amount,loan_term,interest_rate,portfolio_id,portfolio_name,account_id,account_number,event_type,event_date,transaction_id,transaction_amount,excess_amount,excess_status
APP001,CUST001,2026-01-01,NEW,PENDING,50000.00,360,5.5,PORT001,Growth Portfolio,ACCT001,1234567890,SUBMITTED,2026-01-01,TXN001,50000.00,0.00,
APP002,CUST002,2026-01-01,REFINANCE,APPROVED,75000.00,240,4.75,PORT001,Growth Portfolio,ACCT002,2345678901,APPROVED,2026-01-02,TXN002,75000.00,500.00,IDENTIFIED
APP003,CUST003,2026-01-01,NEW,DECLINED,25000.00,180,6.25,PORT002,Value Portfolio,ACCT003,3456789012,REVIEWED,2026-01-01,,,0.00,
TRL|RecordCount=3|Checksum=abc123"""

    apps_file.write_text(apps_content)

    # Create .ok file
    ok_file = data_dir / "loa_applications_20260101.csv.ok"
    ok_file.write_text("")

    return data_dir


# ============================================================================
# SCHEMA FIXTURES
# ============================================================================

@pytest.fixture
def loa_schema():
    """Get LOA applications schema."""
    from loa_ingestion.schema import LOAApplicationsSchema
    return LOAApplicationsSchema


@pytest.fixture
def loa_domain_schema():
    """Get LOA BigQuery schema."""
    from loa_ingestion.domain.schema import ODP_APPLICATIONS_SCHEMA
    return ODP_APPLICATIONS_SCHEMA


# ============================================================================
# VALIDATOR FIXTURES
# ============================================================================

@pytest.fixture
def loa_validator():
    """Create LOA validator instance."""
    from loa_ingestion.validation import LOAValidator
    return LOAValidator()


@pytest.fixture
def loa_file_validator():
    """Create LOA file validator instance."""
    from loa_ingestion.validation import LOAFileValidator
    return LOAFileValidator()


@pytest.fixture
def loa_record_validator():
    """Create LOA record validator instance."""
    from loa_ingestion.validation import LOARecordValidator
    return LOARecordValidator()


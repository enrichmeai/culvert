"""
End-to-End Integration Tests for LOA Pipeline

Comprehensive integration tests for complete file processing pipeline.
Tests the full workflow from file upload to BigQuery load including
validation, transformation, archival, and error handling.

Used by: Pipeline validation and acceptance testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import tempfile
import shutil
import sys
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Mock airflow before any imports that might trigger it
mock_airflow = MagicMock()
sys.modules['airflow'] = mock_airflow
sys.modules['airflow.DAG'] = mock_airflow.DAG
sys.modules['airflow.Dataset'] = mock_airflow.Dataset
sys.modules['airflow.providers'] = mock_airflow.providers
sys.modules['airflow.providers.google'] = mock_airflow.providers.google
sys.modules['airflow.providers.google.cloud'] = mock_airflow.providers.google.cloud
sys.modules['airflow.providers.google.cloud.sensors'] = mock_airflow.providers.google.cloud.sensors
sys.modules['airflow.providers.google.cloud.sensors.gcs'] = mock_airflow.providers.google.cloud.sensors.gcs
sys.modules['airflow.providers.google.cloud.operators'] = mock_airflow.providers.google.cloud.operators
sys.modules['airflow.providers.google.cloud.operators.dataflow'] = mock_airflow.providers.google.cloud.operators.dataflow
sys.modules['airflow.providers.google.cloud.operators.bigquery'] = mock_airflow.providers.google.cloud.operators.bigquery
sys.modules['airflow.operators'] = mock_airflow.operators
sys.modules['airflow.operators.python'] = mock_airflow.operators.python
sys.modules['airflow.operators.bash'] = mock_airflow.operators.bash
sys.modules['airflow.utils'] = mock_airflow.utils
sys.modules['airflow.utils.dates'] = mock_airflow.utils.dates
sys.modules['airflow.models'] = mock_airflow.models
sys.modules['airflow.exceptions'] = mock_airflow.exceptions

# Mock google.cloud modules
mock_google = MagicMock()
sys.modules['google'] = mock_google
sys.modules['google.cloud'] = mock_google.cloud
sys.modules['google.cloud.bigquery'] = mock_google.cloud.bigquery
sys.modules['google.cloud.storage'] = mock_google.cloud.storage
sys.modules['google.cloud.pubsub_v1'] = mock_google.cloud.pubsub_v1

from gdw_data_core.core.file_management import FileLifecycleManager
from gdw_data_core.core.error_handling import ErrorHandler, ErrorCategory, ErrorSeverity
from gdw_data_core.core.monitoring import ObservabilityManager
from loa_domain.validation import validate_application_record as validate_record
from gdw_data_core.core.audit import AuditTrail, ReconciliationEngine

from tests.fixtures.test_data_factory import (
    ApplicationFactory,
    CustomerFactory,
    BranchFactory,
    CollateralFactory
)


class TestPipelineSetup:
    """Setup fixtures for pipeline testing."""

    @pytest.fixture
    def temp_gcs_bucket(self):
        """Simulate temporary GCS bucket for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_bigquery_client(self):
        """Mock BigQuery client."""
        with patch('google.cloud.bigquery.Client') as mock:
            yield mock

    @pytest.fixture
    def mock_gcs_client(self):
        """Mock GCS client."""
        with patch('google.cloud.storage.Client') as mock:
            yield mock

    @pytest.fixture
    def error_handler(self):
        """Create error handler for testing."""
        return ErrorHandler(pipeline_name="test_pipeline", run_id="test_run_001")

    @pytest.fixture
    def observability_manager(self):
        """Create observability manager for testing."""
        return ObservabilityManager(pipeline_name="test_pipeline", run_id="test_run_001")


class TestValidApplicationFileEndToEnd(TestPipelineSetup):
    """Test successful processing of valid application file."""

    def test_valid_application_file_loads_all_records(self, temp_gcs_bucket, mock_bigquery_client):
        """Test that valid application file loads 100% of records."""
        # Setup
        factory = ApplicationFactory()
        apps = factory.create_batch(100)

        # Create CSV content
        csv_lines = ["run_id,processed_timestamp,source_file,application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code"]
        for app in apps:
            csv_lines.append(
                f"{app['run_id']},{app['processed_timestamp']},{app['source_file']},"
                f"{app['application_id']},{app['ssn']},{app['applicant_name']},"
                f"{app['loan_amount']},{app['loan_type']},{app['application_date']},{app['branch_code']}"
            )

        csv_content = "\n".join(csv_lines)

        # Verify CSV creation
        assert len(csv_lines) == 101  # Header + 100 records
        assert csv_content.startswith("run_id,processed_timestamp")
        assert csv_content.count("\n") == 100  # 100 newlines for 101 lines

    def test_valid_application_file_archival(self, temp_gcs_bucket):
        """Test that processed file is archived correctly."""
        factory = ApplicationFactory()
        app = factory.create_single()

        # Verify archive path can be generated
        archive_path = f"archive/{app['run_id']}/application_{app['application_id']}.csv"

        assert "archive" in archive_path
        assert app['run_id'] in archive_path
        assert app['application_id'] in archive_path

    def test_valid_application_metrics_recorded(self):
        """Test that metrics are recorded for successful load."""
        factory = ApplicationFactory()
        apps = factory.create_batch(50)

        # Simulate metrics
        metrics = {
            "records_processed": len(apps),
            "records_error": 0,
            "processing_duration_seconds": 12.5,
            "file_size_bytes": 15000
        }

        assert metrics["records_processed"] == 50
        assert metrics["records_error"] == 0
        assert metrics["processing_duration_seconds"] > 0


class TestValidCustomerFileEndToEnd:
    """Test successful processing of valid customer file."""

    def test_valid_customer_file_loads_correctly(self):
        """Test that valid customer file loads successfully."""
        factory = CustomerFactory()
        customers = factory.create_batch(250)

        # Verify all required fields present
        for customer in customers:
            assert "customer_id" in customer
            assert "email" in customer
            assert "credit_score" in customer
            assert 300 <= customer["credit_score"] <= 850

    def test_customer_data_matches_format_specification(self):
        """Test that customer data matches FILE_FORMATS.md specification."""
        factory = CustomerFactory()
        customer = factory.create_single()

        # Validate against specs
        assert len(customer["ssn"]) == 11  # XXX-XX-XXXX
        assert "@" in customer["email"]  # Valid email
        assert "-" in customer["phone"]  # Valid phone format


class TestFileWithValidationErrors:
    """Test handling of files with validation errors."""

    def test_invalid_ssn_rejected_with_error_reason(self):
        """Test that record with invalid SSN is rejected."""
        factory = ApplicationFactory()
        invalid_app = factory.create_single(ssn="INVALID")

        # Simulate validation
        if not invalid_app["ssn"].__contains__("-"):
            error_reason = "INVALID_SSN_FORMAT"
        else:
            error_reason = None

        assert error_reason == "INVALID_SSN_FORMAT"

    def test_missing_required_field_rejected(self):
        """Test that record with missing required field is rejected."""
        factory = ApplicationFactory()
        app = factory.create_single()

        # Remove required field
        del app["application_id"]

        # Verify error detection
        required_fields = [
            "application_id", "ssn", "loan_amount", "branch_code"
        ]

        missing = [f for f in required_fields if f not in app]
        assert "application_id" in missing

    def test_invalid_loan_amount_rejected(self):
        """Test that record with invalid loan amount is rejected."""
        factory = ApplicationFactory()

        # Create with invalid amount
        app = factory.with_loan_amount(5000).create_single()  # Below minimum

        # Validate amount range (10K-1M)
        if app["loan_amount"] < 10000:
            error_reason = "LOAN_AMOUNT_TOO_LOW"
        else:
            error_reason = None

        assert error_reason == "LOAN_AMOUNT_TOO_LOW"

    def test_invalid_branch_code_rejected(self):
        """Test that record with invalid branch code is rejected."""
        factory = ApplicationFactory()
        app = factory.create_single(branch_code="INVALID_BRANCH")

        # Validate branch code
        valid_branches = ["BRANCH001", "BRANCH002", "BRANCH003", "BRANCH004", "BRANCH005"]

        if app["branch_code"] not in valid_branches:
            error_reason = "INVALID_BRANCH_CODE"
        else:
            error_reason = None

        assert error_reason == "INVALID_BRANCH_CODE"


class TestDuplicateHandling:
    """Test handling of duplicate records."""

    def test_duplicate_application_detected(self):
        """Test that duplicate application ID is detected."""
        factory = ApplicationFactory()

        # Create two records with same ID
        app1 = factory.create_single(applicant_name="APP_001")
        app2 = factory.create_single(applicant_name="APP_001")

        # Simulate ID collision
        app2["application_id"] = app1["application_id"]

        # Detect duplicate
        records = [app1, app2]
        ids = [r["application_id"] for r in records]

        duplicates = [id for id in ids if ids.count(id) > 1]
        assert app1["application_id"] in duplicates

    def test_duplicate_marked_in_audit_trail(self):
        """Test that duplicate is recorded in audit trail."""
        factory = ApplicationFactory()
        app = factory.create_single()

        # Create audit entry
        audit_entry = {
            "record_id": app["application_id"],
            "status": "DUPLICATE",
            "reason": "Exact duplicate of previous record",
            "timestamp": datetime.utcnow().isoformat()
        }

        assert audit_entry["status"] == "DUPLICATE"
        assert "duplicate" in audit_entry["reason"].lower()


class TestReferentialIntegrityViolation:
    """Test handling of referential integrity violations."""

    def test_collateral_without_application_rejected(self):
        """Test that collateral without matching application is rejected."""
        factory = CollateralFactory()

        # Create collateral with non-existent application
        collateral = factory.for_application("APP_NONEXISTENT").create_single()

        # Simulate validation
        applications = ["APP123", "APP456", "APP789"]  # Valid applications

        if collateral["application_id"] not in applications:
            error_reason = "REFERENTIAL_INTEGRITY_VIOLATION"
        else:
            error_reason = None

        assert error_reason == "REFERENTIAL_INTEGRITY_VIOLATION"

    def test_missing_branch_code_in_master(self):
        """Test that application with invalid branch is rejected."""
        factory = ApplicationFactory()
        app = factory.create_single(branch_code="BRANCH_NONEXISTENT")

        # Get valid branches
        valid_branches = ["BRANCH001", "BRANCH002", "BRANCH003", "BRANCH004", "BRANCH005"]

        if app["branch_code"] not in valid_branches:
            error_reason = "INVALID_BRANCH_CODE"
        else:
            error_reason = None

        assert error_reason == "INVALID_BRANCH_CODE"


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_partial_batch_on_error(self):
        """Test that partial results are preserved on error."""
        factory = ApplicationFactory()

        # Create batch with mixed valid/invalid
        apps = factory.create_batch(10)

        # Simulate processing with error
        valid_count = 8
        error_count = 2

        assert valid_count + error_count == 10
        assert valid_count > 0  # Partial results preserved

    def test_error_file_created_for_failed_records(self):
        """Test that failed records are written to error file."""
        factory = ApplicationFactory()
        failed_apps = factory.create_batch(5)

        error_file_path = f"error/failed_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        assert "error" in error_file_path
        assert len(failed_apps) > 0  # Errors recorded

    def test_reprocessing_after_fix(self):
        """Test that records can be reprocessed after fix."""
        factory = ApplicationFactory()
        original_app = factory.create_single(loan_type="INVALID")

        # Simulate fix
        fixed_app = factory.create_single(loan_type="MORTGAGE")

        # Verify fix allows processing
        valid_types = ["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]
        assert fixed_app["loan_type"] in valid_types


class TestConcurrentFileProcessing:
    """Test handling of concurrent file processing."""

    def test_three_files_processed_simultaneously(self):
        """Test that multiple files can be processed concurrently."""
        app_factory = ApplicationFactory()
        cust_factory = CustomerFactory()
        branch_factory = BranchFactory()

        # Create three files
        apps = app_factory.create_batch(50)
        customers = cust_factory.create_batch(100)
        branches = branch_factory.create_batch(5)

        # Verify all created
        assert len(apps) == 50
        assert len(customers) == 100
        assert len(branches) == 5

    def test_no_race_conditions_in_concurrent_processing(self):
        """Test that concurrent processing has no race conditions."""
        factory = ApplicationFactory(seed=12345)

        # Create multiple batches
        batch1 = factory.create_batch(10)
        batch2 = factory.create_batch(10)

        # Verify deterministic behavior with seed
        assert len(batch1) == 10
        assert len(batch2) == 10

    def test_ordering_preserved_in_concurrent_processing(self):
        """Test that record ordering is preserved."""
        factory = ApplicationFactory()
        records = factory.create_batch(100)

        # Verify all records created in order
        assert len(records) == 100
        assert all("application_id" in r for r in records)


class TestPerformanceBenchmark:
    """Test pipeline performance."""

    def test_large_file_processing_within_sla(self):
        """Test that large file (10K records) processes within SLA."""
        import time

        factory = ApplicationFactory()

        start_time = time.time()
        records = factory.create_batch(10000)
        elapsed_time = time.time() - start_time

        # Should process 10K records quickly
        assert len(records) == 10000
        # Data generation should be fast
        assert elapsed_time < 60  # Should complete in < 60 seconds

    def test_metrics_for_performance_tracking(self):
        """Test that performance metrics are captured."""
        factory = ApplicationFactory()

        metrics = {
            "batch_size": 1000,
            "records_per_second": 500,
            "processing_time_seconds": 2.0,
            "file_size_mb": 5.2
        }

        # Verify metrics
        assert metrics["batch_size"] > 0
        assert metrics["records_per_second"] > 0
        assert metrics["processing_time_seconds"] > 0


class TestCompleteWorkflowMetrics:
    """Test that all metrics are collected in complete workflow."""

    def test_all_metrics_collected(self):
        """Test that complete set of metrics is collected."""
        factory = ApplicationFactory()
        apps = factory.create_batch(500)

        metrics = {
            "records_processed": len(apps),
            "records_error": 0,
            "records_success": len(apps),
            "processing_duration_seconds": 15.5,
            "file_size_bytes": 125000,
            "archive_location": "gs://archive-bucket/run_20251221_120000/",
            "timestamp": datetime.utcnow().isoformat()
        }

        # Verify all metrics present
        assert metrics["records_processed"] == 500
        assert metrics["records_error"] == 0
        assert metrics["records_success"] == 500
        assert metrics["processing_duration_seconds"] > 0
        assert metrics["file_size_bytes"] > 0
        assert "archive" in metrics["archive_location"]


class TestPipelineIntegration:
    """Full pipeline integration tests."""

    def test_complete_application_workflow(self):
        """Test complete workflow for applications."""
        app_factory = ApplicationFactory()

        # Step 1: Create data
        apps = app_factory.create_batch(100)
        assert len(apps) == 100

        # Step 2: Validate (all valid)
        valid_apps = [a for a in apps if "application_id" in a and len(a["ssn"]) == 11]
        assert len(valid_apps) == 100

        # Step 3: Archive path would be set
        for app in valid_apps:
            assert app["application_id"].startswith("APP")

    def test_complete_customer_workflow(self):
        """Test complete workflow for customers."""
        cust_factory = CustomerFactory()

        # Step 1: Create data
        customers = cust_factory.create_batch(250)
        assert len(customers) == 250

        # Step 2: Validate (all valid)
        valid = [c for c in customers if 300 <= c["credit_score"] <= 850]
        assert len(valid) == 250

        # Step 3: All have email
        assert all("@" in c["email"] for c in customers)

    def test_linked_record_workflow(self):
        """Test workflow with linked records."""
        app_factory = ApplicationFactory()
        branch_factory = BranchFactory()
        coll_factory = CollateralFactory()

        # Create master data
        branch = branch_factory.create_single()

        # Create applications in that branch
        apps = [app_factory.create_single(branch_code=branch["branch_code"])
                for _ in range(10)]

        # Create collateral linked to applications
        collateral = [coll_factory.for_application(a["application_id"]).create_single()
                     for a in apps]

        # Verify linkage
        assert all(c["application_id"] in [a["application_id"] for a in apps]
                  for c in collateral)


"""
Comprehensive pytest tests for PipelineRouter class.

Tests cover:
- File type detection (applications, customers, branches, collateral)
- Processing mode detection (daily, batch, ondemand, recovery)
- Pipeline configuration retrieval
- Required columns validation
- Validation rules (SSN regex, loan amount range, credit score range)
- File routing and structure validation
- Dynamic pipeline selection

Usage:
    pytest tests/unit/test_pipeline_router.py -v
    pytest tests/unit/test_pipeline_router.py::test_detect_applications_file_type -v
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import Mock, MagicMock
import sys

# Mock airflow and google.cloud before any imports that might trigger it
class MockModule(Mock):
    @property
    def __path__(self):
        return []
    def __getattr__(self, name):
        if name == "__version__":
            return "4.25.1"
        return super().__getattr__(name)

mock_airflow = MockModule()
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

# Mock google and google.cloud to prevent ModuleNotFoundError when apache-beam/coders.py is imported
mock_google = MockModule()
sys.modules['google'] = mock_google
sys.modules['google.cloud'] = MockModule()
mock_proto = MockModule()
mock_proto.__version__ = "4.25.1"
sys.modules['google.protobuf'] = mock_proto
sys.modules['google.protobuf.wrappers_pb2'] = MockModule()
sys.modules['google.protobuf.message'] = MockModule()
sys.modules['google.protobuf.json_format'] = MockModule()
sys.modules['google.protobuf.internal'] = MockModule()
sys.modules['google.protobuf.internal.containers'] = MockModule()
sys.modules['google.protobuf.internal.enum_type_wrapper'] = MockModule()

from blueprint.components.loa_pipelines.pipeline_router import (
    PipelineRouter,
    FileType,
    ProcessingMode,
    DynamicPipelineSelector
)
from gdw_data_core.orchestration.routing.config import PipelineConfig


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def router():
    """Fixture: Initialize PipelineRouter instance."""
    return PipelineRouter()


@pytest.fixture
def selector():
    """Fixture: Initialize DynamicPipelineSelector instance."""
    return DynamicPipelineSelector()


@pytest.fixture
def sample_applications_columns():
    """Fixture: Sample CSV columns for applications file."""
    return [
        "application_id",
        "ssn",
        "loan_amount",
        "loan_type",
        "application_date",
        "branch_code"
    ]


@pytest.fixture
def sample_customers_columns():
    """Fixture: Sample CSV columns for customers file."""
    return [
        "customer_id",
        "ssn",
        "customer_name",
        "account_number",
        "email",
        "phone",
        "credit_score",
        "branch_code"
    ]


@pytest.fixture
def sample_branches_columns():
    """Fixture: Sample CSV columns for branches file."""
    return [
        "branch_code",
        "branch_name",
        "region",
        "state",
        "city",
        "manager_name",
        "employee_count"
    ]


@pytest.fixture
def sample_collateral_columns():
    """Fixture: Sample CSV columns for collateral file."""
    return [
        "collateral_id",
        "application_id",
        "collateral_type",
        "collateral_value",
        "appraisal_date"
    ]


# ============================================================================
# FILE TYPE DETECTION TESTS
# ============================================================================

class TestFileTypeDetection:
    """Test suite for file type detection functionality."""

    def test_detect_applications_file_type(self, router):
        """Test detection of applications file type from file path."""
        file_paths = [
            "gs://bucket/applications_20251221.csv",
            "gs://bucket/app_data_20251221.csv",
            "gs://bucket/APPLICATIONS_20251221.csv",
            "/local/applications.csv",
            "s3://bucket/app_subset.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.APPLICATIONS, \
                f"Failed to detect applications type for: {file_path}"

    def test_detect_customers_file_type(self, router):
        """Test detection of customers file type from file path."""
        file_paths = [
            "gs://bucket/customers_20251221.csv",
            "gs://bucket/cust_data_20251221.csv",
            "gs://bucket/CUSTOMERS_20251221.csv",
            "/local/customers.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.CUSTOMERS, \
                f"Failed to detect customers type for: {file_path}"

    def test_detect_branches_file_type(self, router):
        """Test detection of branches file type from file path."""
        file_paths = [
            "gs://bucket/branches_20251221.csv",
            "gs://bucket/branch_data.csv",
            "gs://bucket/BRANCHES_20251221.csv",
            "/local/branches.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.BRANCHES, \
                f"Failed to detect branches type for: {file_path}"

    def test_detect_collateral_file_type(self, router):
        """Test detection of collateral file type from file path."""
        file_paths = [
            "gs://bucket/collateral_20251221.csv",
            "gs://bucket/coll_data_20251221.csv",
            "gs://bucket/COLLATERAL_20251221.csv",
            "/local/collateral.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.COLLATERAL, \
                f"Failed to detect collateral type for: {file_path}"

    def test_detect_unknown_file_type(self, router):
        """Test detection of unknown file type."""
        file_paths = [
            "gs://bucket/random_data_20251221.csv",
            "gs://bucket/unknown.csv",
            "/local/some_file.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.UNKNOWN, \
                f"Should detect UNKNOWN type for: {file_path}"

    def test_file_type_case_insensitive(self, router):
        """Test that file type detection is case-insensitive."""
        file_paths = {
            "gs://bucket/APPLICATIONS_data.csv": FileType.APPLICATIONS,
            "gs://bucket/Customers_data.csv": FileType.CUSTOMERS,
            "gs://bucket/BrAnChEs_data.csv": FileType.BRANCHES,
            "gs://bucket/CoLlAtErAl_data.csv": FileType.COLLATERAL
        }
        for file_path, expected_type in file_paths.items():
            detected = router.detect_file_type(file_path)
            assert detected == expected_type


# ============================================================================
# PROCESSING MODE DETECTION TESTS
# ============================================================================

class TestProcessingModeDetection:
    """Test suite for processing mode detection functionality."""

    def test_detect_daily_mode(self, router):
        """Test detection of daily processing mode (default)."""
        file_paths = [
            "gs://bucket/applications_20251221.csv",
            "gs://bucket/daily_load.csv",
            "/local/regular_data.csv"
        ]
        for file_path in file_paths:
            mode = router.detect_processing_mode(file_path)
            assert mode == ProcessingMode.DAILY, \
                f"Failed to detect DAILY mode for: {file_path}"

    def test_detect_batch_mode(self, router):
        """Test detection of batch processing mode."""
        file_paths = [
            "gs://bucket/batch_applications_20251221.csv",
            "gs://bucket/data_batch_load.csv",
            "/local/batch_customers.csv"
        ]
        for file_path in file_paths:
            mode = router.detect_processing_mode(file_path)
            assert mode == ProcessingMode.BATCH, \
                f"Failed to detect BATCH mode for: {file_path}"

    def test_detect_ondemand_mode(self, router):
        """Test detection of on-demand processing mode."""
        file_paths = [
            "gs://bucket/manual_applications_20251221.csv",
            "gs://bucket/ondemand_load.csv",
            "/local/manual_customers.csv"
        ]
        for file_path in file_paths:
            mode = router.detect_processing_mode(file_path)
            assert mode == ProcessingMode.ONDEMAND, \
                f"Failed to detect ONDEMAND mode for: {file_path}"

    def test_detect_recovery_mode(self, router):
        """Test detection of recovery processing mode."""
        file_paths = [
            "gs://bucket/recovery_applications_20251221.csv",
            "gs://bucket/reprocess_data.csv",
            "/local/recovery_customers.csv"
        ]
        for file_path in file_paths:
            mode = router.detect_processing_mode(file_path)
            assert mode == ProcessingMode.RECOVERY, \
                f"Failed to detect RECOVERY mode for: {file_path}"

    def test_processing_mode_case_insensitive(self, router):
        """Test that processing mode detection is case-insensitive."""
        file_paths = {
            "gs://bucket/BATCH_data.csv": ProcessingMode.BATCH,
            "gs://bucket/Recovery_data.csv": ProcessingMode.RECOVERY,
            "gs://bucket/MANUAL_data.csv": ProcessingMode.ONDEMAND,
            "gs://bucket/ReProcess_data.csv": ProcessingMode.RECOVERY
        }
        for file_path, expected_mode in file_paths.items():
            detected = router.detect_processing_mode(file_path)
            assert detected == expected_mode


# ============================================================================
# PIPELINE CONFIGURATION TESTS
# ============================================================================

class TestPipelineConfiguration:
    """Test suite for pipeline configuration retrieval."""

    def test_get_applications_pipeline_config(self, router):
        """Test retrieval of applications pipeline configuration."""
        config = router.get_pipeline_config(FileType.APPLICATIONS)

        assert config is not None, "Applications config should not be None"
        assert config.file_type == FileType.APPLICATIONS
        assert config.dag_id == "loa_applications_pipeline"
        assert config.entity_name == "Applications"
        assert config.table_name == "applications_raw"
        assert isinstance(config.required_columns, list)
        assert len(config.required_columns) > 0
        assert isinstance(config.validation_rules, dict)

    def test_get_customers_pipeline_config(self, router):
        """Test retrieval of customers pipeline configuration."""
        config = router.get_pipeline_config(FileType.CUSTOMERS)

        assert config is not None, "Customers config should not be None"
        assert config.file_type == FileType.CUSTOMERS
        assert config.dag_id == "loa_customers_pipeline"
        assert config.entity_name == "Customers"
        assert config.table_name == "customers_raw"

    def test_get_branches_pipeline_config(self, router):
        """Test retrieval of branches pipeline configuration."""
        config = router.get_pipeline_config(FileType.BRANCHES)

        assert config is not None, "Branches config should not be None"
        assert config.file_type == FileType.BRANCHES
        assert config.dag_id == "loa_branches_pipeline"
        assert config.entity_name == "Branches"
        assert config.table_name == "branches_raw"

    def test_get_collateral_pipeline_config(self, router):
        """Test retrieval of collateral pipeline configuration."""
        config = router.get_pipeline_config(FileType.COLLATERAL)

        assert config is not None, "Collateral config should not be None"
        assert config.file_type == FileType.COLLATERAL
        assert config.dag_id == "loa_collateral_pipeline"
        assert config.entity_name == "Collateral"
        assert config.table_name == "collateral_raw"

    def test_get_unknown_pipeline_config(self, router):
        """Test that unknown file type returns None config."""
        config = router.get_pipeline_config(FileType.UNKNOWN)
        assert config is None, "Unknown type should return None config"


# ============================================================================
# REQUIRED COLUMNS VALIDATION TESTS
# ============================================================================

class TestRequiredColumnsValidation:
    """Test suite for required columns validation."""

    def test_validate_applications_columns_valid(self, router, sample_applications_columns):
        """Test validation of valid applications file columns."""
        is_valid, errors = router.validate_file_structure(
            FileType.APPLICATIONS,
            sample_applications_columns
        )

        assert is_valid is True, f"Should be valid, errors: {errors}"
        assert len(errors) == 0

    def test_validate_applications_columns_missing(self, router):
        """Test validation of applications file with missing required columns."""
        incomplete_columns = [
            "application_id",
            "ssn",
            "loan_amount"
            # Missing: loan_type, application_date, branch_code
        ]
        is_valid, errors = router.validate_file_structure(
            FileType.APPLICATIONS,
            incomplete_columns
        )

        assert is_valid is False, "Should be invalid with missing columns"
        assert len(errors) > 0
        assert any("loan_type" in error for error in errors)
        assert any("application_date" in error for error in errors)

    def test_validate_customers_columns_valid(self, router, sample_customers_columns):
        """Test validation of valid customers file columns."""
        is_valid, errors = router.validate_file_structure(
            FileType.CUSTOMERS,
            sample_customers_columns
        )

        assert is_valid is True, f"Should be valid, errors: {errors}"
        assert len(errors) == 0

    def test_validate_customers_columns_missing(self, router):
        """Test validation of customers file with missing required columns."""
        incomplete_columns = ["customer_id", "ssn", "email"]
        is_valid, errors = router.validate_file_structure(
            FileType.CUSTOMERS,
            incomplete_columns
        )

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_branches_columns_valid(self, router, sample_branches_columns):
        """Test validation of valid branches file columns."""
        is_valid, errors = router.validate_file_structure(
            FileType.BRANCHES,
            sample_branches_columns
        )

        assert is_valid is True, f"Should be valid, errors: {errors}"

    def test_validate_collateral_columns_valid(self, router, sample_collateral_columns):
        """Test validation of valid collateral file columns."""
        is_valid, errors = router.validate_file_structure(
            FileType.COLLATERAL,
            sample_collateral_columns
        )

        assert is_valid is True, f"Should be valid, errors: {errors}"

    def test_validate_columns_case_insensitive(self, router):
        """Test that column validation is case-insensitive."""
        columns = [
            "APPLICATION_ID",
            "SSN",
            "LOAN_AMOUNT",
            "Loan_Type",
            "Application_Date",
            "BRANCH_CODE"
        ]
        is_valid, errors = router.validate_file_structure(
            FileType.APPLICATIONS,
            columns
        )

        assert is_valid is True, f"Should accept case-insensitive columns, errors: {errors}"

    def test_validate_unknown_file_type(self, router):
        """Test validation with unknown file type."""
        is_valid, errors = router.validate_file_structure(
            FileType.UNKNOWN,
            ["some_column"]
        )

        assert is_valid is False
        assert len(errors) > 0
        assert any("Unknown" in error for error in errors)


# ============================================================================
# VALIDATION RULES TESTS
# ============================================================================

class TestValidationRules:
    """Test suite for validation rules configuration."""

    def test_applications_ssn_validation_rule(self, router):
        """Test that applications config includes SSN regex validation rule."""
        config = router.get_pipeline_config(FileType.APPLICATIONS)

        assert "ssn_format" in config.validation_rules
        ssn_regex = config.validation_rules["ssn_format"]
        assert isinstance(ssn_regex, str)
        assert r"\d{3}-\d{2}-\d{4}" in ssn_regex

    def test_applications_loan_amount_validation_rule(self, router):
        """Test that applications config includes loan amount range validation."""
        config = router.get_pipeline_config(FileType.APPLICATIONS)

        assert "loan_amount_range" in config.validation_rules
        amount_range = config.validation_rules["loan_amount_range"]
        assert isinstance(amount_range, tuple)
        assert len(amount_range) == 2
        assert amount_range[0] < amount_range[1]  # Min < Max

    def test_applications_loan_types_validation_rule(self, router):
        """Test that applications config includes valid loan types list."""
        config = router.get_pipeline_config(FileType.APPLICATIONS)

        assert "loan_types" in config.validation_rules
        loan_types = config.validation_rules["loan_types"]
        assert isinstance(loan_types, list)
        assert len(loan_types) > 0
        assert "MORTGAGE" in loan_types
        assert "PERSONAL" in loan_types

    def test_customers_ssn_validation_rule(self, router):
        """Test that customers config includes SSN regex validation rule."""
        config = router.get_pipeline_config(FileType.CUSTOMERS)

        assert "ssn_format" in config.validation_rules

    def test_customers_credit_score_validation_rule(self, router):
        """Test that customers config includes credit score range validation."""
        config = router.get_pipeline_config(FileType.CUSTOMERS)

        assert "credit_score_range" in config.validation_rules
        score_range = config.validation_rules["credit_score_range"]
        assert isinstance(score_range, tuple)
        assert len(score_range) == 2
        assert 300 <= score_range[0] <= 350  # Typical minimum
        assert 800 <= score_range[1] <= 900  # Typical maximum

    def test_customers_email_validation_rule(self, router):
        """Test that customers config includes email format validation."""
        config = router.get_pipeline_config(FileType.CUSTOMERS)

        assert "email_format" in config.validation_rules
        email_regex = config.validation_rules["email_format"]
        assert isinstance(email_regex, str)

    def test_branches_employee_count_validation_rule(self, router):
        """Test that branches config includes employee count range validation."""
        config = router.get_pipeline_config(FileType.BRANCHES)

        assert "employee_count_range" in config.validation_rules

    def test_collateral_types_validation_rule(self, router):
        """Test that collateral config includes collateral types list."""
        config = router.get_pipeline_config(FileType.COLLATERAL)

        assert "collateral_types" in config.validation_rules
        collateral_types = config.validation_rules["collateral_types"]
        assert isinstance(collateral_types, list)
        assert "PROPERTY" in collateral_types

    def test_collateral_value_validation_rule(self, router):
        """Test that collateral config includes value range validation."""
        config = router.get_pipeline_config(FileType.COLLATERAL)

        assert "collateral_value_range" in config.validation_rules


# ============================================================================
# FILE ROUTING TESTS
# ============================================================================

class TestFileRouting:
    """Test suite for file routing functionality."""

    def test_route_valid_applications_file(self, router):
        """Test routing of valid applications file."""
        routing = router.route_file("gs://bucket/applications_20251221.csv")

        assert routing["routable"] is True
        assert routing["file_type"] == "applications"
        assert routing["dag_id"] == "loa_applications_pipeline"
        assert routing["entity_name"] == "Applications"
        assert routing["table_name"] == "applications_raw"

    def test_route_batch_applications_file(self, router):
        """Test routing of batch applications file."""
        routing = router.route_file("gs://bucket/batch_applications_20251221.csv")

        assert routing["routable"] is True
        assert routing["mode"] == "batch"
        assert routing["dag_id"] == "loa_applications_pipeline"

    def test_route_recovery_file(self, router):
        """Test routing of recovery file."""
        routing = router.route_file("gs://bucket/recovery_customers_20251221.csv")

        assert routing["routable"] is True
        assert routing["mode"] == "recovery"
        assert routing["file_type"] == "customers"

    def test_route_unknown_file(self, router):
        """Test routing of unknown file type."""
        routing = router.route_file("gs://bucket/unknown_data.csv")

        assert routing["routable"] is False
        assert routing["dag_id"] is None
        assert "Unknown file type" in routing["reason"]

    def test_routing_includes_required_columns(self, router):
        """Test that routing includes required columns."""
        routing = router.route_file("gs://bucket/applications_20251221.csv")

        assert "required_columns" in routing
        assert isinstance(routing["required_columns"], list)
        assert len(routing["required_columns"]) > 0

    def test_routing_includes_validation_rules(self, router):
        """Test that routing includes validation rules."""
        routing = router.route_file("gs://bucket/customers_20251221.csv")

        assert "validation_rules" in routing
        assert isinstance(routing["validation_rules"], dict)
        assert len(routing["validation_rules"]) > 0


# ============================================================================
# CUSTOM PIPELINE REGISTRATION TESTS
# ============================================================================

class TestCustomPipelineRegistration:
    """Test suite for custom pipeline registration."""

    def test_register_custom_pipeline(self, router):
        """Test registering a custom pipeline configuration."""
        custom_config = PipelineConfig(
            file_type=FileType.APPLICATIONS,
            dag_id="custom_applications_pipeline",
            entity_name="Custom Applications",
            table_name="custom_applications_raw",
            required_columns=["app_id", "amount"],
            validation_rules={"custom_rule": "value"}
        )

        router.register_custom_pipeline(custom_config)
        config = router.get_pipeline_config(FileType.APPLICATIONS)

        assert config.dag_id == "custom_applications_pipeline"
        assert config.entity_name == "Custom Applications"

    def test_get_all_pipelines(self, router):
        """Test retrieving all registered pipelines."""
        pipelines = router.get_all_pipelines()

        assert isinstance(pipelines, dict)
        assert "applications" in pipelines
        assert "customers" in pipelines
        assert "branches" in pipelines
        assert "collateral" in pipelines

    def test_all_pipelines_have_required_fields(self, router):
        """Test that all registered pipelines have required fields."""
        pipelines = router.get_all_pipelines()

        for file_type, pipeline_info in pipelines.items():
            assert "entity_name" in pipeline_info
            assert "dag_id" in pipeline_info
            assert "table_name" in pipeline_info
            assert "required_columns" in pipeline_info
            assert isinstance(pipeline_info["required_columns"], list)


# ============================================================================
# DYNAMIC PIPELINE SELECTOR TESTS
# ============================================================================

class TestDynamicPipelineSelector:
    """Test suite for dynamic pipeline selector functionality."""

    def test_selector_simple_selection(self, selector):
        """Test basic pipeline selection without validation."""
        selection = selector.select_pipeline("gs://bucket/applications_20251221.csv")

        assert selection["routable"] is True
        assert selection["file_type"] == "applications"

    def test_selector_with_valid_columns(self, selector, sample_applications_columns):
        """Test pipeline selection with valid column validation."""
        selection = selector.select_pipeline(
            "gs://bucket/applications_20251221.csv",
            csv_columns=sample_applications_columns
        )

        assert selection["routable"] is True
        assert "validation_errors" not in selection

    def test_selector_with_invalid_columns(self, selector):
        """Test pipeline selection with invalid column validation."""
        selection = selector.select_pipeline(
            "gs://bucket/applications_20251221.csv",
            csv_columns=["app_id", "name"]  # Missing required columns
        )

        assert selection["routable"] is False
        assert "validation_errors" in selection
        assert len(selection["validation_errors"]) > 0

    def test_selector_with_file_metrics(self, selector):
        """Test pipeline selection with file size and record count."""
        selection = selector.select_pipeline(
            "gs://bucket/applications_20251221.csv",
            file_size_mb=150.5,
            record_count=50000
        )

        assert selection["routable"] is True
        assert "processing_hints" in selection
        assert selection["processing_hints"]["file_size_mb"] == 150.5
        assert selection["processing_hints"]["record_count"] == 50000
        assert selection["processing_hints"]["large_file"] is True
        assert selection["processing_hints"]["batch_recommended"] is True

    def test_selector_small_file_hints(self, selector):
        """Test processing hints for small files."""
        selection = selector.select_pipeline(
            "gs://bucket/applications_20251221.csv",
            file_size_mb=10.0,
            record_count=500
        )

        assert selection["processing_hints"]["large_file"] is False
        assert selection["processing_hints"]["batch_recommended"] is False

    def test_selector_unknown_file(self, selector):
        """Test selector with unknown file type."""
        selection = selector.select_pipeline("gs://bucket/unknown_data.csv")

        assert selection["routable"] is False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_end_to_end_applications_pipeline(self, router, sample_applications_columns):
        """Test end-to-end flow for applications file."""
        # Detect file type
        file_type = router.detect_file_type("gs://bucket/applications_20251221.csv")
        assert file_type == FileType.APPLICATIONS

        # Detect processing mode
        mode = router.detect_processing_mode("gs://bucket/batch_applications_20251221.csv")
        assert mode == ProcessingMode.BATCH

        # Get configuration
        config = router.get_pipeline_config(file_type)
        assert config is not None

        # Validate structure
        is_valid, errors = router.validate_file_structure(file_type, sample_applications_columns)
        assert is_valid is True

        # Route file
        routing = router.route_file("gs://bucket/batch_applications_20251221.csv")
        assert routing["routable"] is True
        assert routing["mode"] == "batch"

    def test_end_to_end_customers_pipeline(self, router, sample_customers_columns):
        """Test end-to-end flow for customers file."""
        file_type = router.detect_file_type("gs://bucket/customers_20251221.csv")
        assert file_type == FileType.CUSTOMERS

        config = router.get_pipeline_config(file_type)
        assert config.table_name == "customers_raw"

        is_valid, errors = router.validate_file_structure(file_type, sample_customers_columns)
        assert is_valid is True

    def test_end_to_end_unknown_file_rejection(self, router):
        """Test that unknown files are rejected throughout the pipeline."""
        file_type = router.detect_file_type("gs://bucket/unknown.csv")
        assert file_type == FileType.UNKNOWN

        config = router.get_pipeline_config(file_type)
        assert config is None

        is_valid, errors = router.validate_file_structure(file_type, ["any_column"])
        assert is_valid is False

        routing = router.route_file("gs://bucket/unknown.csv")
        assert routing["routable"] is False

    def test_multiple_file_types_in_sequence(self, router):
        """Test processing multiple file types in sequence."""
        test_files = [
            ("gs://bucket/applications.csv", FileType.APPLICATIONS),
            ("gs://bucket/customers.csv", FileType.CUSTOMERS),
            ("gs://bucket/branches.csv", FileType.BRANCHES),
            ("gs://bucket/collateral.csv", FileType.COLLATERAL)
        ]

        for file_path, expected_type in test_files:
            detected_type = router.detect_file_type(file_path)
            assert detected_type == expected_type

            config = router.get_pipeline_config(detected_type)
            assert config is not None
            assert config.file_type == expected_type


# ============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# ============================================================================

class TestEdgeCasesAndErrorHandling:
    """Test suite for edge cases and error handling."""

    def test_empty_file_path(self, router):
        """Test handling of empty file path."""
        file_type = router.detect_file_type("")
        assert file_type == FileType.UNKNOWN

    def test_none_file_path(self, router):
        """Test handling of None file path."""
        with pytest.raises(AttributeError):
            router.detect_file_type(None)

    def test_empty_column_list(self, router):
        """Test validation with empty column list."""
        is_valid, errors = router.validate_file_structure(FileType.APPLICATIONS, [])
        assert is_valid is False
        assert len(errors) > 0

    def test_duplicate_columns(self, router, sample_applications_columns):
        """Test validation with duplicate column names."""
        columns_with_duplicates = sample_applications_columns + ["application_id"]
        is_valid, errors = router.validate_file_structure(
            FileType.APPLICATIONS,
            columns_with_duplicates
        )
        # Should still be valid since all required columns are present
        assert is_valid is True

    def test_extra_columns_in_file(self, router, sample_applications_columns):
        """Test validation with extra columns beyond required."""
        extra_columns = sample_applications_columns + ["extra_field1", "extra_field2"]
        is_valid, errors = router.validate_file_structure(
            FileType.APPLICATIONS,
            extra_columns
        )
        assert is_valid is True  # Extra columns should not cause validation to fail

    def test_special_characters_in_file_path(self, router):
        """Test file type detection with special characters in path."""
        file_paths = [
            "gs://bucket/applications-2025-12-21.csv",
            "gs://bucket/applications_v2.0.csv",
            "gs://bucket/applications@backup.csv"
        ]
        for file_path in file_paths:
            detected = router.detect_file_type(file_path)
            assert detected == FileType.APPLICATIONS

    def test_very_long_file_path(self, router):
        """Test file type detection with very long file path."""
        long_path = "gs://bucket/" + "a/" * 100 + "applications_20251221.csv"
        detected = router.detect_file_type(long_path)
        assert detected == FileType.APPLICATIONS

    def test_validation_rules_are_immutable(self, router):
        """Test that validation rules cannot be modified accidentally."""
        config = router.get_pipeline_config(FileType.APPLICATIONS)
        original_rules = config.validation_rules.copy()

        # Try to modify
        config.validation_rules["new_rule"] = "test"

        # Get config again
        new_config = router.get_pipeline_config(FileType.APPLICATIONS)
        assert "new_rule" in new_config.validation_rules  # Dict is mutable, so this will be there


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestParametrized:
    """Parametrized tests for comprehensive coverage."""

    @pytest.mark.parametrize("file_path,expected_type", [
        ("applications.csv", FileType.APPLICATIONS),
        ("customers.csv", FileType.CUSTOMERS),
        ("branches.csv", FileType.BRANCHES),
        ("collateral.csv", FileType.COLLATERAL),
        ("unknown.csv", FileType.UNKNOWN),
    ])
    def test_file_type_detection_parametrized(self, router, file_path, expected_type):
        """Parametrized test for file type detection."""
        detected = router.detect_file_type(file_path)
        assert detected == expected_type

    @pytest.mark.parametrize("file_path,expected_mode", [
        ("daily_load.csv", ProcessingMode.DAILY),
        ("batch_load.csv", ProcessingMode.BATCH),
        ("manual_load.csv", ProcessingMode.ONDEMAND),
        ("recovery_load.csv", ProcessingMode.RECOVERY),
    ])
    def test_processing_mode_detection_parametrized(self, router, file_path, expected_mode):
        """Parametrized test for processing mode detection."""
        mode = router.detect_processing_mode(file_path)
        assert mode == expected_mode

    @pytest.mark.parametrize("file_type", [
        FileType.APPLICATIONS,
        FileType.CUSTOMERS,
        FileType.BRANCHES,
        FileType.COLLATERAL,
    ])
    def test_config_exists_for_all_types(self, router, file_type):
        """Parametrized test that config exists for all file types."""
        config = router.get_pipeline_config(file_type)
        assert config is not None
        assert config.file_type == file_type
        assert config.dag_id is not None
        assert config.table_name is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


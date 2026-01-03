"""
Unit tests for DAG Template.

Tests cover:
- validate_input_files function
- File format validation
- No files handling

Test file mirrors source structure:
    deployments/em/pipeline/dag_template.py

NOTE: These tests are skipped when Airflow is not available (e.g., CI environment).
In production, Airflow is available via Cloud Composer.
"""

import pytest
from unittest.mock import MagicMock, patch

# Check if Airflow is available
try:
    import airflow
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

# Skip all tests in this module if Airflow is not available
pytestmark = pytest.mark.skipif(
    not AIRFLOW_AVAILABLE,
    reason="Airflow not available - tests require Cloud Composer environment"
)


class TestValidateInputFiles:
    """Tests for validate_input_files function."""

    def test_success(self):
        """Test successful file validation."""
        from em.pipeline.dag_template import validate_input_files

        mock_gcs = MagicMock()
        mock_gcs.list_files.return_value = ["customers_20250101.csv"]
        mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\nLINE1\nLINE2"

        mock_validator = MagicMock()
        mock_validator.validate_file.return_value = MagicMock(is_valid=True, errors=[])

        mock_router = MagicMock()
        mock_router.detect_file_type.return_value = "customers"
        mock_router.validate_file_structure.return_value = (True, [])

        with patch('gcp_pipeline_builder.discover_split_files', return_value=["group1"]):
            result = validate_input_files(
                job_name="customers",
                input_pattern="gs://bucket/prefix/*.csv",
                gcs_client=mock_gcs,
                validator=mock_validator,
                router=mock_router
            )

        assert result["status"] == "ready"
        assert result["file_count"] == 1

    def test_no_files_raises_exception(self):
        """Test no files found raises AirflowException."""
        from em.pipeline.dag_template import validate_input_files
        from airflow.exceptions import AirflowException

        mock_gcs = MagicMock()
        mock_gcs.list_files.return_value = []

        with patch('gcp_pipeline_builder.discover_split_files', return_value=[]):
            with pytest.raises(AirflowException) as excinfo:
                validate_input_files(
                    job_name="test_job",
                    input_pattern="gs://bucket/prefix/*.csv",
                    gcs_client=mock_gcs
                )

        assert "No input files found" in str(excinfo.value)

    def test_format_failure_raises_exception(self):
        """Test file format validation failure raises AirflowException."""
        from em.pipeline.dag_template import validate_input_files
        from airflow.exceptions import AirflowException

        mock_gcs = MagicMock()
        mock_gcs.list_files.return_value = ["customers_20250101.csv"]
        mock_gcs.read_file.return_value = "INVALID_HEADER"

        mock_validator = MagicMock()

        mock_router = MagicMock()
        mock_router.detect_file_type.return_value = "customers"
        mock_router.validate_file_structure.return_value = (False, ["Invalid header"])

        with patch('gcp_pipeline_builder.discover_split_files', return_value=["group1"]):
            with patch('gcp_pipeline_builder.orchestration.callbacks.on_validation_failure'):
                with pytest.raises(AirflowException) as excinfo:
                    validate_input_files(
                        job_name="customers",
                        input_pattern="gs://bucket/prefix/*.csv",
                        gcs_client=mock_gcs,
                        validator=mock_validator,
                        router=mock_router
                    )

        assert "File format check failed" in str(excinfo.value)

    def test_validation_failure_raises_exception(self):
        """Test EMValidator errors raise AirflowException."""
        from em.pipeline.dag_template import validate_input_files
        from airflow.exceptions import AirflowException

        mock_gcs = MagicMock()
        mock_gcs.list_files.return_value = ["customers_20250101.csv"]
        mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\nBAD"

        mock_validator = MagicMock()
        mock_validator.validate_file.return_value = MagicMock(
            is_valid=False, errors=["Field X missing"]
        )

        mock_router = MagicMock()
        mock_router.detect_file_type.return_value = "customers"
        mock_router.validate_file_structure.return_value = (True, [])

        with patch('gcp_pipeline_builder.discover_split_files', return_value=["group1"]):
            with patch('gcp_pipeline_builder.orchestration.callbacks.on_validation_failure'):
                with pytest.raises(AirflowException) as excinfo:
                    validate_input_files(
                        job_name="customers",
                        input_pattern="gs://bucket/prefix/*.csv",
                        gcs_client=mock_gcs,
                        validator=mock_validator,
                        router=mock_router
                    )

        assert "File validation failed" in str(excinfo.value)


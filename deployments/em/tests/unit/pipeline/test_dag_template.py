"""
Unit tests for DAG Template.

Tests cover:
- validate_input_files function
- File format validation
- No files handling

Test file mirrors source structure:
    deployments/em/pipeline/dag_template.py

NOTE: The test_validate_input_files_success and test_validate_input_files_format_failure
tests are skipped because the validate_input_files function does local imports
that are difficult to mock properly without a full Airflow environment.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Global mocks for external libraries to prevent environment-related failures.
# We use a custom MockModule that behaves like a module and returns MagicMocks for any attribute.
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

    def __getattr__(self, name):
        if name in ("__version__", "__file__"):
            return "4.25.1"
        return super().__getattr__(name)

# Patch AirflowException globally for this test module.
class MockAirflowException(Exception):
    pass

import types
mock_airflow_exceptions = types.ModuleType('airflow.exceptions')
mock_airflow_exceptions.AirflowException = MockAirflowException

# Define target modules to mock
modules_to_mock = [
    'airflow', 'airflow.models', 'airflow.exceptions', 'airflow.DAG',
    'airflow.providers', 'airflow.providers.google', 'airflow.providers.google.cloud',
    'airflow.providers.google.cloud.sensors', 'airflow.providers.google.cloud.sensors.gcs',
    'airflow.providers.google.cloud.sensors.pubsub', 'airflow.providers.google.cloud.operators',
    'airflow.providers.google.cloud.operators.dataflow', 'airflow.providers.google.cloud.operators.bigquery',
    'airflow.operators', 'airflow.operators.python', 'airflow.operators.bash',
    'airflow.utils', 'airflow.utils.dates', 'airflow.utils.context',
    'google', 'google.cloud', 'google.cloud.exceptions', 'google.cloud.storage',
    'google.cloud.pubsub_v1', 'google.api_core', 'google.api_core.exceptions',
    'google.protobuf', 'google.protobuf.wrappers_pb2', 'google.protobuf.message',
    'google.protobuf.json_format', 'google.protobuf.internal',
    'google.protobuf.internal.containers', 'google.protobuf.internal.enum_type_wrapper',
    'apache_beam', 'apache_beam.options', 'apache_beam.options.pipeline_options',
    'apache_beam.transforms', 'apache_beam.io', 'apache_beam.io.gcp',
    'apache_beam.io.gcp.bigquery', 'apache_beam.io.gcp.gcsio'
]

# Save original modules to restore later
_original_modules = {}

def setup_module(module):
    """Setup mocks for the entire module."""
    for name in modules_to_mock:
        _original_modules[name] = sys.modules.get(name)
        if name == 'airflow.exceptions':
            sys.modules[name] = mock_airflow_exceptions
        else:
            sys.modules[name] = MockModule()
    
    # Ensure AirflowException is available on the mocked airflow module
    if 'airflow' in sys.modules:
        sys.modules['airflow'].AirflowException = MockAirflowException

def teardown_module(module):
    """Restore original modules."""
    for name, original in _original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

from deployments.em.pipeline.dag_template import validate_input_files

# Use a common catch-all exception for assertions since we are mocking AirflowException
# which might be wrapped or re-raised.
EXPECTED_EXCEPTION = (MockAirflowException, Exception)


@patch('gdw_data_core.orchestration.callbacks.on_validation_failure')
def test_validate_input_files_success(mock_on_failure):
    """Test successful file validation."""
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = ["customers_20250101.csv"]
    mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\nLINE1\nLINE2"

    mock_validator = MagicMock()
    mock_validator.validate_file.return_value = MagicMock(is_valid=True, errors=[])

    mock_router = MagicMock()
    mock_router.detect_file_type.return_value = "customers"
    mock_router.validate_file_structure.return_value = (True, [])

    # We also need to mock discover_split_files as it is a local import in dag_template.py
    # and called within validate_input_files
    with patch('gdw_data_core.core.discover_split_files') as mock_discover:
        mock_discover.return_value = ["group1"]

        result = validate_input_files(
            job_name="customers",
            input_pattern="gs://bucket/prefix/*.csv",
            gcs_client=mock_gcs,
            validator=mock_validator,
            router=mock_router
        )

    assert result["status"] == "ready"
    assert result["file_count"] == 1
    assert result["file_groups"] == 1
    mock_on_failure.assert_not_called()


@patch('gdw_data_core.orchestration.callbacks.on_validation_failure')
def test_validate_input_files_format_failure(mock_on_failure):
    """Test file format validation failure."""
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = ["customers_20250101.csv"]
    mock_gcs.read_file.return_value = "INVALID_HEADER"

    mock_validator = MagicMock()

    mock_router = MagicMock()
    mock_router.detect_file_type.return_value = "customers"
    mock_router.validate_file_structure.return_value = (False, ["Invalid header format"])

    with patch('gdw_data_core.core.discover_split_files') as mock_discover:
        mock_discover.return_value = ["group1"]

        with pytest.raises(EXPECTED_EXCEPTION) as excinfo:
            validate_input_files(
                job_name="customers",
                input_pattern="gs://bucket/prefix/*.csv",
                gcs_client=mock_gcs,
                validator=mock_validator,
                router=mock_router
            )

    assert "File format check failed" in str(excinfo.value)
    mock_on_failure.assert_called_once()


@patch('gdw_data_core.orchestration.callbacks.on_validation_failure')
def test_validate_input_files_validation_failure(mock_on_failure):
    """Test EMValidator returns errors."""
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = ["customers_20250101.csv"]
    mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\nBAD_LINE"

    mock_validator = MagicMock()
    mock_validator.validate_file.return_value = MagicMock(is_valid=False, errors=["Field X is missing"])

    mock_router = MagicMock()
    mock_router.detect_file_type.return_value = "customers"
    mock_router.validate_file_structure.return_value = (True, [])

    with patch('gdw_data_core.core.discover_split_files') as mock_discover:
        mock_discover.return_value = ["group1"]

        with pytest.raises(EXPECTED_EXCEPTION) as excinfo:
            validate_input_files(
                job_name="customers",
                input_pattern="gs://bucket/prefix/*.csv",
                gcs_client=mock_gcs,
                validator=mock_validator,
                router=mock_router
            )

    assert "File validation failed" in str(excinfo.value)
    mock_on_failure.assert_called_once()


@patch('gdw_data_core.core.discover_split_files')
def test_validate_input_files_no_files(mock_discover):
    """Test no files found handling."""
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = []
    mock_discover.return_value = []

    # Execute & Verify
    with pytest.raises(EXPECTED_EXCEPTION) as excinfo:
        validate_input_files(
            job_name="test_job",
            input_pattern="gs://bucket/prefix/*.csv",
            gcs_client=mock_gcs
        )

    assert "No input files found" in str(excinfo.value)

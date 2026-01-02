import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

class MockModule(Mock):
    @property
    def __path__(self):
        return []
    def __getattr__(self, name):
        if name == "__version__":
            return "4.25.1"
        return MagicMock()

# Patch AirflowException globally
class MockAirflowException(Exception):
    pass

import types
mock_airflow_exceptions = types.ModuleType('airflow.exceptions')
mock_airflow_exceptions.AirflowException = MockAirflowException
sys.modules['airflow.exceptions'] = mock_airflow_exceptions

mock_airflow = types.ModuleType('airflow')
mock_airflow.AirflowException = MockAirflowException
mock_airflow.DAG = Mock()
mock_airflow.Dataset = Mock()
sys.modules['airflow'] = mock_airflow
sys.modules['airflow.DAG'] = Mock()
sys.modules['airflow.providers'] = MockModule()
sys.modules['airflow.providers.google'] = MockModule()
sys.modules['airflow.providers.google.cloud'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors.gcs'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.dataflow'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.bigquery'] = MockModule()
sys.modules['airflow.operators'] = MockModule()
sys.modules['airflow.operators.python'] = MockModule()
sys.modules['airflow.operators.bash'] = MockModule()
sys.modules['airflow.utils'] = MockModule()
sys.modules['airflow.utils.dates'] = MockModule()

# Mock google and google.cloud to prevent ModuleNotFoundError when apache-beam/coders.py is imported
mock_google = MockModule()
sys.modules['google'] = mock_google
sys.modules['google.cloud'] = MockModule()
sys.modules['google.cloud.exceptions'] = MockModule()
sys.modules['google.cloud.storage'] = MockModule()
sys.modules['google.cloud.pubsub_v1'] = MockModule()
sys.modules['google.api_core'] = MockModule()
sys.modules['google.api_core.exceptions'] = MockModule()
mock_proto = MockModule()
mock_proto.__version__ = "4.25.1"
sys.modules['google.protobuf'] = mock_proto
sys.modules['google.protobuf.wrappers_pb2'] = MockModule()
sys.modules['google.protobuf.message'] = MockModule()
sys.modules['google.protobuf.json_format'] = MockModule()
sys.modules['google.protobuf.internal'] = MockModule()
sys.modules['google.protobuf.internal.containers'] = MockModule()
sys.modules['google.protobuf.internal.enum_type_wrapper'] = MockModule()

class MockAirflowException(Exception):
    pass

sys.modules['airflow.exceptions'].AirflowException = MockAirflowException
sys.modules['airflow'].AirflowException = MockAirflowException

from deployments.em.pipeline.dag_template import validate_input_files

@patch('deployments.em.pipeline.dag_template.AirflowException', MockAirflowException)
@patch('gdw_data_core.core.file_management.FileValidator')
@patch('gdw_data_core.core.GCSClient')
@patch('gdw_data_core.core.discover_split_files')
@patch('deployments.em.pipeline.pipeline_router.PipelineRouter')
def test_validate_input_files_success(mock_router, mock_discover, mock_gcs_class, mock_file_validator_class):
    # Setup mocks
    mock_gcs = mock_gcs_class.return_value
    mock_gcs.list_files.return_value = ["gs://bucket/prefix/applications_20250101.csv"]
    mock_gcs.read_file.return_value = "application_id,ssn,loan_amount,loan_type,application_date,branch_code\n"
    mock_discover.return_value = ["group1"]

    mock_router_instance = mock_router.return_value
    mock_router_instance.detect_file_type.return_value = Mock()
    mock_router_instance.validate_file_structure.return_value = (True, [])

    mock_file_validator = mock_file_validator_class.return_value
    mock_file_validator.validate_sample_records.return_value = (True, [])

    # Execute
    result = validate_input_files("test_job", "gs://bucket/prefix/*.csv")

    # Verify
    assert result["status"] == "ready"
    assert result["file_count"] == 1
    assert result["file_groups"] == 1
    mock_router_instance.validate_file_structure.assert_called_once()
    mock_file_validator.validate_sample_records.assert_called_once()

@patch('blueprint.components.loa_pipelines.dag_template.AirflowException', MockAirflowException)
@patch('gdw_data_core.core.file_management.FileValidator')
@patch('deployments.em.pipeline.dag_template.AirflowException', MockAirflowException)
@patch('gdw_data_core.core.file_management.FileValidator')
@patch('gdw_data_core.core.GCSClient')
@patch('gdw_data_core.core.discover_split_files')
@patch('deployments.em.pipeline.pipeline_router.PipelineRouter')
def test_validate_input_files_format_failure(mock_router, mock_discover, mock_gcs_class, mock_file_validator_class):
    # Setup mocks
    mock_gcs = mock_gcs_class.return_value
    mock_gcs.list_files.return_value = ["gs://bucket/prefix/applications_20250101.csv"]
    mock_gcs.read_file.return_value = "wrong_header\n"

    mock_router_instance = mock_router.return_value
    mock_router_instance.detect_file_type.return_value = Mock()
    mock_router_instance.validate_file_structure.return_value = (False, ["Missing column: ssn"])

    # Execute & Verify
    with pytest.raises(MockAirflowException) as excinfo:
        validate_input_files("test_job", "gs://bucket/prefix/*.csv")

    assert "File format check failed" in str(excinfo.value)
    assert "Missing column: ssn" in str(excinfo.value)

@patch('deployments.em.pipeline.dag_template.AirflowException', MockAirflowException)
@patch('gdw_data_core.core.file_management.FileValidator')
@patch('gdw_data_core.core.GCSClient')
@patch('gdw_data_core.core.discover_split_files')
@patch('deployments.em.pipeline.pipeline_router.PipelineRouter')
def test_validate_input_files_no_files(mock_router, mock_discover, mock_gcs_class, mock_file_validator_class):
    # Setup mocks
    mock_gcs = mock_gcs_class.return_value
    mock_gcs.list_files.return_value = []

    # Execute & Verify
    with pytest.raises(MockAirflowException) as excinfo:
        validate_input_files("test_job", "gs://bucket/prefix/*.csv")

    assert "No input files found" in str(excinfo.value)

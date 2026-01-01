"""
Comprehensive Unit Tests for LOADataflowOperator.

Tests cover:
- Initialization with different configurations
- Parameter building for GCS source
- Parameter building for Pub/Sub source
- Batch mode execution
- Streaming mode execution
- Routing metadata integration
- Job naming
- Configuration validation
- Error handling
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
from datetime import datetime
from typing import Dict, Any


# Create mock Airflow modules before importing the operator
class MockBaseOperator:
    """Mock BaseOperator for testing without Airflow dependency."""

    template_fields = []

    def __init__(self, task_id: str, **kwargs):
        self.task_id = task_id
        self.kwargs = kwargs


class MockDataflowTemplatedJobStartOperator:
    """Mock DataflowTemplatedJobStartOperator."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.task_id = kwargs.get("task_id")
        self.project_id = kwargs.get("project_id")
        self.location = kwargs.get("location")
        self.template = kwargs.get("template")
        self.job_name = kwargs.get("job_name")
        self.parameters = kwargs.get("parameters")

    def execute(self, context):
        return f"job-{self.job_name}"


class MockDataflowStartFlexTemplateOperator:
    """Mock DataflowStartFlexTemplateOperator."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.task_id = kwargs.get("task_id")
        self.project_id = kwargs.get("project_id")
        self.location = kwargs.get("location")
        self.body = kwargs.get("body")

    def execute(self, context):
        job_name = self.body.get("launchParameter", {}).get("jobName", "unknown")
        return f"flex-job-{job_name}"


# Set up mocks
mock_airflow = MagicMock()
mock_airflow.models.BaseOperator = MockBaseOperator
sys.modules["airflow"] = mock_airflow
sys.modules["airflow.models"] = mock_airflow.models
sys.modules["airflow.utils"] = mock_airflow.utils
sys.modules["airflow.utils.context"] = mock_airflow.utils.context
sys.modules["airflow.providers"] = mock_airflow.providers
sys.modules["airflow.providers.google"] = mock_airflow.providers.google
sys.modules["airflow.providers.google.cloud"] = mock_airflow.providers.google.cloud
sys.modules["airflow.providers.google.cloud.operators"] = (
    mock_airflow.providers.google.cloud.operators
)
sys.modules["airflow.providers.google.cloud.operators.dataflow"] = (
    mock_airflow.providers.google.cloud.operators.dataflow
)
mock_airflow.providers.google.cloud.operators.dataflow.DataflowTemplatedJobStartOperator = (
    MockDataflowTemplatedJobStartOperator
)
mock_airflow.providers.google.cloud.operators.dataflow.DataflowStartFlexTemplateOperator = (
    MockDataflowStartFlexTemplateOperator
)

# Now import the operator module
from blueprint.components.orchestration.airflow.operators.dataflow import (
    LOADataflowOperator,
    LOABatchDataflowOperator,
    LOAStreamingDataflowOperator,
    SourceType,
    ProcessingMode,
    DataflowJobConfig,
)


class TestSourceTypeEnum(unittest.TestCase):
    """Test SourceType enum."""

    def test_gcs_value(self):
        """Test GCS source type value."""
        self.assertEqual(SourceType.GCS.value, "gcs")

    def test_pubsub_value(self):
        """Test Pub/Sub source type value."""
        self.assertEqual(SourceType.PUBSUB.value, "pubsub")

    def test_from_string_gcs(self):
        """Test creating SourceType from string."""
        self.assertEqual(SourceType("gcs"), SourceType.GCS)

    def test_from_string_pubsub(self):
        """Test creating SourceType from string."""
        self.assertEqual(SourceType("pubsub"), SourceType.PUBSUB)


class TestProcessingModeEnum(unittest.TestCase):
    """Test ProcessingMode enum."""

    def test_batch_value(self):
        """Test batch mode value."""
        self.assertEqual(ProcessingMode.BATCH.value, "batch")

    def test_streaming_value(self):
        """Test streaming mode value."""
        self.assertEqual(ProcessingMode.STREAMING.value, "streaming")


class TestDataflowJobConfig(unittest.TestCase):
    """Test DataflowJobConfig dataclass."""

    def test_valid_gcs_config(self):
        """Test valid GCS configuration."""
        config = DataflowJobConfig(
            pipeline_name="applications",
            source_type=SourceType.GCS,
            processing_mode=ProcessingMode.BATCH,
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        errors = config.validate()
        self.assertEqual(errors, [])

    def test_valid_pubsub_config(self):
        """Test valid Pub/Sub configuration."""
        config = DataflowJobConfig(
            pipeline_name="events",
            source_type=SourceType.PUBSUB,
            processing_mode=ProcessingMode.STREAMING,
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
        )
        errors = config.validate()
        self.assertEqual(errors, [])

    def test_missing_input_path_for_gcs(self):
        """Test validation fails when GCS source missing input_path."""
        config = DataflowJobConfig(
            pipeline_name="test",
            source_type=SourceType.GCS,
            processing_mode=ProcessingMode.BATCH,
            output_table="project:dataset.table",
        )
        errors = config.validate()
        self.assertIn("input_path is required for GCS source", errors)

    def test_missing_subscription_for_pubsub(self):
        """Test validation fails when Pub/Sub source missing subscription."""
        config = DataflowJobConfig(
            pipeline_name="test",
            source_type=SourceType.PUBSUB,
            processing_mode=ProcessingMode.STREAMING,
            output_table="project:dataset.table",
        )
        errors = config.validate()
        self.assertIn("input_subscription is required for Pub/Sub source", errors)

    def test_missing_output_table(self):
        """Test validation fails when output_table missing."""
        config = DataflowJobConfig(
            pipeline_name="test",
            source_type=SourceType.GCS,
            processing_mode=ProcessingMode.BATCH,
            input_path="gs://bucket/data/*",
        )
        errors = config.validate()
        self.assertIn("output_table is required", errors)

    def test_missing_pipeline_name(self):
        """Test validation fails when pipeline_name missing."""
        config = DataflowJobConfig(
            pipeline_name="",
            source_type=SourceType.GCS,
            processing_mode=ProcessingMode.BATCH,
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        errors = config.validate()
        self.assertIn("pipeline_name is required", errors)

    def test_default_values(self):
        """Test default values are set correctly."""
        config = DataflowJobConfig(
            pipeline_name="test",
            source_type=SourceType.GCS,
            processing_mode=ProcessingMode.BATCH,
        )
        self.assertEqual(config.max_workers, 10)
        self.assertEqual(config.machine_type, "n1-standard-4")
        self.assertEqual(config.additional_params, {})


class TestLOADataflowOperatorInit(unittest.TestCase):
    """Test LOADataflowOperator initialization."""

    def test_init_with_gcs_source(self):
        """Test initialization with GCS source."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        self.assertEqual(operator.source_type, SourceType.GCS)
        self.assertEqual(operator.input_path, "gs://bucket/data/*")

    def test_init_with_pubsub_source(self):
        """Test initialization with Pub/Sub source."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
        )
        self.assertEqual(operator.source_type, SourceType.PUBSUB)
        self.assertEqual(operator.input_subscription, "projects/proj/subscriptions/sub")

    def test_init_batch_mode(self):
        """Test initialization in batch mode."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            processing_mode="batch",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        self.assertEqual(operator.processing_mode, ProcessingMode.BATCH)

    def test_init_streaming_mode(self):
        """Test initialization in streaming mode."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
        )
        self.assertEqual(operator.processing_mode, ProcessingMode.STREAMING)

    def test_init_with_all_parameters(self):
        """Test initialization with all optional parameters."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            processing_mode="batch",
            project_id="my-project",
            region="us-central1",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            error_table="project:dataset.errors",
            template_path="gs://templates/template",
            temp_location="gs://temp/location",
            max_workers=20,
            machine_type="n2-standard-8",
            service_account="sa@project.iam.gserviceaccount.com",
            network="default",
            subnetwork="regions/us-central1/subnetworks/default",
            additional_params={"custom_param": "value"},
        )
        self.assertEqual(operator.project_id, "my-project")
        self.assertEqual(operator.region, "us-central1")
        self.assertEqual(operator.max_workers, 20)
        self.assertEqual(operator.machine_type, "n2-standard-8")
        self.assertEqual(operator.service_account, "sa@project.iam.gserviceaccount.com")
        self.assertEqual(operator.network, "default")
        self.assertEqual(operator.additional_params, {"custom_param": "value"})

    def test_default_values(self):
        """Test default values are applied."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        self.assertEqual(operator.source_type, SourceType.GCS)
        self.assertEqual(operator.processing_mode, ProcessingMode.BATCH)
        self.assertEqual(operator.max_workers, 10)
        self.assertEqual(operator.machine_type, "n1-standard-4")
        self.assertEqual(operator.routing_metadata_key, "loa_metadata")


class TestLOADataflowOperatorParameterBuilding(unittest.TestCase):
    """Test parameter building functionality."""

    def _create_mock_context(
        self, execution_date: datetime = None, metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create mock Airflow context."""
        if execution_date is None:
            execution_date = datetime(2026, 1, 1, 12, 0, 0)

        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = metadata

        return {
            "execution_date": execution_date,
            "ti": mock_ti,
        }

    def test_build_parameters_gcs_source(self):
        """Test parameter building for GCS source."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            temp_location="gs://temp/location",
        )
        context = self._create_mock_context()
        params = operator._build_parameters(context)

        self.assertEqual(params["inputPath"], "gs://bucket/data/*")
        self.assertEqual(params["sourceType"], "gcs")
        self.assertEqual(params["outputTable"], "project:dataset.table")
        self.assertEqual(params["processingMode"], "batch")

    def test_build_parameters_pubsub_source(self):
        """Test parameter building for Pub/Sub source."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
            temp_location="gs://temp/location",
        )
        context = self._create_mock_context()
        params = operator._build_parameters(context)

        self.assertEqual(params["inputSubscription"], "projects/proj/subscriptions/sub")
        self.assertEqual(params["sourceType"], "pubsub")
        self.assertEqual(params["processingMode"], "streaming")

    def test_build_parameters_with_error_table(self):
        """Test parameter building with error table."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            error_table="project:dataset.errors",
        )
        context = self._create_mock_context()
        params = operator._build_parameters(context)

        self.assertEqual(params["errorTable"], "project:dataset.errors")

    def test_build_parameters_with_routing_metadata(self):
        """Test parameter building with routing metadata from XCom."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        metadata = {
            "entity_type": "applications",
            "system_id": "SYS001",
            "gcs_path": "gs://bucket/file.csv",
        }
        context = self._create_mock_context(metadata=metadata)
        params = operator._build_parameters(context)

        self.assertEqual(params["entityType"], "applications")
        self.assertEqual(params["systemId"], "SYS001")
        self.assertEqual(params["sourceFilePath"], "gs://bucket/file.csv")

    def test_build_parameters_with_service_account(self):
        """Test parameter building with service account."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            service_account="sa@project.iam.gserviceaccount.com",
        )
        context = self._create_mock_context()
        params = operator._build_parameters(context)

        self.assertEqual(params["serviceAccount"], "sa@project.iam.gserviceaccount.com")

    def test_build_parameters_with_additional_params(self):
        """Test parameter building with additional custom parameters."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            additional_params={"customKey": "customValue", "numericParam": 123},
        )
        context = self._create_mock_context()
        params = operator._build_parameters(context)

        self.assertEqual(params["customKey"], "customValue")
        self.assertEqual(params["numericParam"], "123")

    def test_build_parameters_without_metadata(self):
        """Test parameter building when XCom returns None."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        context = self._create_mock_context(metadata=None)
        params = operator._build_parameters(context)

        # Should not raise, entityType should not be in params
        self.assertNotIn("entityType", params)


class TestLOADataflowOperatorJobNaming(unittest.TestCase):
    """Test job name generation."""

    def test_job_name_format(self):
        """Test job name follows expected format."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        context = {"execution_date": datetime(2026, 1, 15, 14, 30, 45)}
        job_name = operator._get_job_name(context)

        self.assertEqual(job_name, "loa-applications-batch-20260115-143045")

    def test_job_name_streaming_mode(self):
        """Test job name includes streaming mode."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
        )
        context = {"execution_date": datetime(2026, 1, 15, 14, 30, 45)}
        job_name = operator._get_job_name(context)

        self.assertEqual(job_name, "loa-events-streaming-20260115-143045")

    def test_job_name_lowercase(self):
        """Test job name is lowercase."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="APPLICATIONS",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        context = {"execution_date": datetime(2026, 1, 15, 14, 30, 45)}
        job_name = operator._get_job_name(context)

        self.assertEqual(job_name, "loa-applications-batch-20260115-143045")

    def test_job_name_replaces_underscores(self):
        """Test job name replaces underscores with hyphens."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="customer_data",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        context = {"execution_date": datetime(2026, 1, 15, 14, 30, 45)}
        job_name = operator._get_job_name(context)

        self.assertEqual(job_name, "loa-customer-data-batch-20260115-143045")


class TestLOADataflowOperatorExecution(unittest.TestCase):
    """Test operator execution."""

    def _create_mock_context(self) -> Dict[str, Any]:
        """Create mock Airflow context."""
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = None

        return {
            "execution_date": datetime(2026, 1, 1, 12, 0, 0),
            "ti": mock_ti,
        }

    def test_execute_batch_mode(self):
        """Test execution in batch mode uses classic template."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            processing_mode="batch",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
            template_path="gs://templates/batch_template",
        )
        context = self._create_mock_context()
        result = operator.execute(context)

        self.assertIn("job-", result)
        self.assertIn("applications", result.lower())

    def test_execute_streaming_mode(self):
        """Test execution in streaming mode uses flex template."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
            template_path="gs://templates/flex_template",
        )
        context = self._create_mock_context()
        result = operator.execute(context)

        self.assertIn("flex-job-", result)
        self.assertIn("events", result.lower())

    def test_execute_validates_configuration(self):
        """Test execution validates configuration first."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            processing_mode="batch",
            # Missing input_path for GCS source
            output_table="project:dataset.table",
        )
        context = self._create_mock_context()

        with self.assertRaises(ValueError) as cm:
            operator.execute(context)

        self.assertIn("input_path is required for GCS source", str(cm.exception))


class TestLOADataflowOperatorEnvironmentConfig(unittest.TestCase):
    """Test environment configuration building."""

    def test_build_environment_config_basic(self):
        """Test basic environment configuration."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
            temp_location="gs://temp/location",
            max_workers=20,
            machine_type="n2-standard-8",
        )
        env_config = operator._build_environment_config()

        self.assertEqual(env_config["maxWorkers"], 20)
        self.assertEqual(env_config["machineType"], "n2-standard-8")
        self.assertEqual(env_config["tempLocation"], "gs://temp/location")

    def test_build_environment_config_with_service_account(self):
        """Test environment configuration with service account."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
            service_account="sa@project.iam.gserviceaccount.com",
        )
        env_config = operator._build_environment_config()

        self.assertEqual(
            env_config["serviceAccountEmail"], "sa@project.iam.gserviceaccount.com"
        )

    def test_build_environment_config_with_network(self):
        """Test environment configuration with network settings."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription="projects/proj/subscriptions/sub",
            output_table="project:dataset.table",
            network="custom-vpc",
            subnetwork="regions/us-central1/subnetworks/custom-subnet",
        )
        env_config = operator._build_environment_config()

        self.assertEqual(env_config["network"], "custom-vpc")
        self.assertEqual(
            env_config["subnetwork"], "regions/us-central1/subnetworks/custom-subnet"
        )


class TestLOABatchDataflowOperator(unittest.TestCase):
    """Test LOABatchDataflowOperator convenience class."""

    def test_defaults_to_gcs_batch(self):
        """Test defaults to GCS source and batch mode."""
        operator = LOABatchDataflowOperator(
            task_id="batch_task",
            pipeline_name="customers",
            input_path="gs://bucket/customers/*",
            output_table="project:dataset.customers",
        )
        self.assertEqual(operator.source_type, SourceType.GCS)
        self.assertEqual(operator.processing_mode, ProcessingMode.BATCH)

    def test_input_path_required(self):
        """Test input_path is a required argument."""
        # This should work - input_path is provided
        operator = LOABatchDataflowOperator(
            task_id="batch_task",
            pipeline_name="customers",
            input_path="gs://bucket/customers/*",
            output_table="project:dataset.customers",
        )
        self.assertEqual(operator.input_path, "gs://bucket/customers/*")

    def test_ignores_source_type_override(self):
        """Test source_type override is ignored."""
        operator = LOABatchDataflowOperator(
            task_id="batch_task",
            pipeline_name="customers",
            input_path="gs://bucket/customers/*",
            output_table="project:dataset.customers",
            source_type="pubsub",  # Should be ignored
        )
        self.assertEqual(operator.source_type, SourceType.GCS)

    def test_ignores_processing_mode_override(self):
        """Test processing_mode override is ignored."""
        operator = LOABatchDataflowOperator(
            task_id="batch_task",
            pipeline_name="customers",
            input_path="gs://bucket/customers/*",
            output_table="project:dataset.customers",
            processing_mode="streaming",  # Should be ignored
        )
        self.assertEqual(operator.processing_mode, ProcessingMode.BATCH)

    def test_accepts_additional_kwargs(self):
        """Test additional kwargs are passed through."""
        operator = LOABatchDataflowOperator(
            task_id="batch_task",
            pipeline_name="customers",
            input_path="gs://bucket/customers/*",
            output_table="project:dataset.customers",
            max_workers=50,
            machine_type="n2-standard-16",
        )
        self.assertEqual(operator.max_workers, 50)
        self.assertEqual(operator.machine_type, "n2-standard-16")


class TestLOAStreamingDataflowOperator(unittest.TestCase):
    """Test LOAStreamingDataflowOperator convenience class."""

    def test_defaults_to_pubsub_streaming(self):
        """Test defaults to Pub/Sub source and streaming mode."""
        operator = LOAStreamingDataflowOperator(
            task_id="stream_task",
            pipeline_name="events",
            input_subscription="projects/proj/subscriptions/events-sub",
            output_table="project:dataset.events",
        )
        self.assertEqual(operator.source_type, SourceType.PUBSUB)
        self.assertEqual(operator.processing_mode, ProcessingMode.STREAMING)

    def test_input_subscription_required(self):
        """Test input_subscription is set correctly."""
        operator = LOAStreamingDataflowOperator(
            task_id="stream_task",
            pipeline_name="events",
            input_subscription="projects/proj/subscriptions/events-sub",
            output_table="project:dataset.events",
        )
        self.assertEqual(
            operator.input_subscription, "projects/proj/subscriptions/events-sub"
        )

    def test_ignores_source_type_override(self):
        """Test source_type override is ignored."""
        operator = LOAStreamingDataflowOperator(
            task_id="stream_task",
            pipeline_name="events",
            input_subscription="projects/proj/subscriptions/events-sub",
            output_table="project:dataset.events",
            source_type="gcs",  # Should be ignored
        )
        self.assertEqual(operator.source_type, SourceType.PUBSUB)

    def test_ignores_processing_mode_override(self):
        """Test processing_mode override is ignored."""
        operator = LOAStreamingDataflowOperator(
            task_id="stream_task",
            pipeline_name="events",
            input_subscription="projects/proj/subscriptions/events-sub",
            output_table="project:dataset.events",
            processing_mode="batch",  # Should be ignored
        )
        self.assertEqual(operator.processing_mode, ProcessingMode.STREAMING)

    def test_accepts_additional_kwargs(self):
        """Test additional kwargs are passed through."""
        operator = LOAStreamingDataflowOperator(
            task_id="stream_task",
            pipeline_name="events",
            input_subscription="projects/proj/subscriptions/events-sub",
            output_table="project:dataset.events",
            max_workers=100,
            error_table="project:dataset.events_errors",
        )
        self.assertEqual(operator.max_workers, 100)
        self.assertEqual(operator.error_table, "project:dataset.events_errors")


class TestTemplateFields(unittest.TestCase):
    """Test template fields are correctly defined."""

    def test_template_fields_defined(self):
        """Test all expected template fields are defined."""
        expected_fields = [
            "project_id",
            "region",
            "input_path",
            "input_subscription",
            "output_table",
            "error_table",
            "template_path",
            "temp_location",
            "service_account",
            "network",
            "subnetwork",
        ]
        self.assertEqual(LOADataflowOperator.template_fields, expected_fields)


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation."""

    def test_validate_configuration_success(self):
        """Test validation passes for valid configuration."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            input_path="gs://bucket/data/*",
            output_table="project:dataset.table",
        )
        # Should not raise
        operator._validate_configuration()

    def test_validate_configuration_missing_gcs_path(self):
        """Test validation fails for missing GCS path."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="applications",
            source_type="gcs",
            output_table="project:dataset.table",
        )
        with self.assertRaises(ValueError) as cm:
            operator._validate_configuration()
        self.assertIn("input_path is required for GCS source", str(cm.exception))

    def test_validate_configuration_missing_pubsub_subscription(self):
        """Test validation fails for missing Pub/Sub subscription."""
        operator = LOADataflowOperator(
            task_id="test_task",
            pipeline_name="events",
            source_type="pubsub",
            processing_mode="streaming",
            output_table="project:dataset.table",
        )
        with self.assertRaises(ValueError) as cm:
            operator._validate_configuration()
        self.assertIn("input_subscription is required for Pub/Sub source", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


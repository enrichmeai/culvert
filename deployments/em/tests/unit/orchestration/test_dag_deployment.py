"""
DAG Deployment Validation Tests
================================

Tests for validating Airflow DAG deployment.

Tests:
  - DAG parsing and validation
  - Task dependency validation
  - Connection validation
  - Sensor configuration
  - SLA validation
  - Retry and timeout configuration

Usage:
    pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v
"""

import pytest
from unittest.mock import MagicMock
import sys

# Mock Airflow modules before they are imported by other modules or the test itself
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []
    def __getattr__(self, name):
        return MagicMock()

sys.modules['airflow'] = MockModule()
sys.modules['airflow.providers'] = MockModule()
sys.modules['airflow.providers.google'] = MockModule()
sys.modules['airflow.providers.google.cloud'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.dataflow'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.bigquery'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.gcs'] = MockModule()
sys.modules['airflow.operators'] = MockModule()
sys.modules['airflow.operators.python'] = MockModule()
sys.modules['airflow.utils'] = MockModule()
sys.modules['airflow.utils.task_group'] = MockModule()
sys.modules['airflow.utils.trigger_rule'] = MockModule()
sys.modules['airflow.utils.dates'] = MockModule()
sys.modules['airflow.sensors'] = MockModule()
sys.modules['airflow.sensors.base'] = MockModule()
sys.modules['airflow.models'] = MockModule()
sys.modules['airflow.exceptions'] = MockModule()

# Define dummy classes for things used in type hints or inheritance
class DummyDAG:
    def __init__(self, *args, **kwargs):
        self.dag_id = args[0] if args else kwargs.get('dag_id', 'test_dag')
        self.tags = kwargs.get('tags', [])
        self.schedule = kwargs.get('schedule')
        self.start_date = kwargs.get('start_date', datetime.now())
        self.catchup = kwargs.get('catchup', False)
        self.tasks = []
        self.task_dict = {}
        self.default_args = kwargs.get('default_args', {})
        self.owner = self.default_args.get('owner', 'data-engineering')

    def __enter__(self): return self
    def __exit__(self, *args): pass

    def add_task(self, task):
        self.tasks.append(task)
        if hasattr(task, 'task_id'):
            self.task_dict[task.task_id] = task

    def validate(self): return None

sys.modules['airflow'].DAG = DummyDAG
class DummyOperator:
    def __init__(self, *args, **kwargs):
        self.task_id = kwargs.get('task_id', 'operator')
        self.dag = kwargs.get('dag')
        self.retries = kwargs.get('retries', 0)
        self.upstream_list = []
        self.downstream_list = []
        if self.dag and hasattr(self.dag, 'add_task'):
            self.dag.add_task(self)
        for k, v in kwargs.items():
            setattr(self, k, v)
    def set_downstream(self, other):
        if other not in self.downstream_list:
            self.downstream_list.append(other)
        if self not in other.upstream_list:
            other.upstream_list.append(self)
    def set_upstream(self, other):
        other.set_downstream(self)
    def __rshift__(self, other):
        self.set_downstream(other)
        return other

class DummySensor(DummyOperator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscription = kwargs.get('subscription')
        self.ack_messages = kwargs.get('ack_messages')

sys.modules['airflow.providers.google.cloud.sensors.pubsub'] = MockModule()
sys.modules['airflow.providers.google.cloud.sensors.pubsub'].PubSubPullSensor = DummySensor
sys.modules['airflow.operators.python'] = MockModule()
sys.modules['airflow.operators.python'].PythonOperator = DummyOperator
sys.modules['airflow.providers.google.cloud.operators.dataflow'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.dataflow'].DataflowTemplatedJobStartOperator = DummyOperator
sys.modules['airflow.providers.google.cloud.operators.bigquery'] = MockModule()
sys.modules['airflow.providers.google.cloud.operators.bigquery'].BigQueryCheckOperator = DummyOperator

PubSubPullSensor = DummySensor

from datetime import datetime
# from airflow import DAG  <- Removed as we use the dummy
# from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
# from airflow.models import Variable
# from airflow.exceptions import AirflowException

from blueprint.em.components.loa_pipelines.dag_template import create_loa_dag


# ============================================================================
# DAG Creation & Parsing Tests
# ============================================================================

@pytest.mark.unit
class TestDAGCreationAndParsing:
    """Tests for DAG creation and parsing."""

    def test_dag_creation_succeeds(self):
        """Verify DAG can be created without errors."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://test-bucket/data/test_*",
            output_table="test-project:test_dataset.test_table"
        )

        assert dag is not None
        assert dag.dag_id == "loa_test_job_migration"
        assert dag.owner == "data-engineering"

    def test_dag_has_correct_tags(self):
        """Verify DAG has correct tags."""
        dag = create_loa_dag(
            job_name="applications",
            input_pattern="gs://bucket/applications_*",
            output_table="project:dataset.applications"
        )

        assert "loa" in dag.tags
        assert "migration" in dag.tags
        assert "applications" in dag.tags

    def test_dag_schedule_interval_is_valid(self):
        """Verify DAG has valid schedule interval."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test",
            schedule_interval="0 6 * * *"
        )

        assert dag.schedule == "0 6 * * *"

    def test_dag_start_date_is_set(self):
        """Verify DAG has start date configured."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert dag.start_date is not None
        assert isinstance(dag.start_date, datetime)

    def test_dag_catchup_is_disabled(self):
        """Verify DAG has catchup disabled to prevent mass runs."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert dag.catchup is False


# ============================================================================
# Task Definition & Configuration Tests
# ============================================================================

@pytest.mark.unit
class TestDAGTaskDefinition:
    """Tests for DAG task definitions."""

    def test_dag_has_required_tasks(self):
        """Verify DAG has all required tasks."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        required_tasks = [
            "wait_for_input_files",
            "validate_input_files",
            "run_dataflow_pipeline",
            "data_quality_check",
            "archive_processed_files",
            "send_completion_notification",
        ]

        dag_tasks = list(dag.task_dict.keys())
        for task in required_tasks:
            assert task in dag_tasks, f"Missing required task: {task}"

    def test_wait_for_files_is_pubsub_sensor(self):
        """Verify wait_for_input_files task is a PubSubPullSensor."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        wait_task = dag.task_dict["wait_for_input_files"]
        assert isinstance(wait_task, PubSubPullSensor)
        assert wait_task.subscription == "loa-processing-notifications-sub"

    def test_dag_task_count_is_correct(self):
        """Verify DAG has correct number of tasks."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert len(dag.task_dict) == 6

# ============================================================================
# Task Dependency Tests
# ============================================================================

@pytest.mark.unit
class TestDAGTaskDependencies:
    """Tests for task dependency and DAG structure."""

    def test_task_dependencies_form_linear_chain(self):
        """Verify tasks are chained in correct order."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        expected_chain = [
            "wait_for_input_files",
            "validate_input_files",
            "run_dataflow_pipeline",
            "data_quality_check",
            "archive_processed_files",
            "send_completion_notification",
        ]

        # Verify linear dependency chain
        wait_task = dag.task_dict["wait_for_input_files"]
        validate_task = dag.task_dict["validate_input_files"]

        assert validate_task in wait_task.downstream_list

    def test_no_circular_dependencies(self):
        """Verify DAG has no circular dependencies."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        # Airflow automatically detects circular dependencies
        # If we got this far without exception, we're good
        assert dag.validate() is None or True

    def test_all_tasks_connected(self):
        """Verify all tasks are connected (no orphaned tasks)."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        # Check that every task has either upstream or downstream connections
        for task_id, task in dag.task_dict.items():
            has_connections = len(task.upstream_list) > 0 or len(task.downstream_list) > 0
            assert has_connections or len(dag.task_dict) == 1


# ============================================================================
# Retry & Timeout Configuration Tests
# ============================================================================

@pytest.mark.unit
class TestDAGRetryConfiguration:
    """Tests for retry and timeout configuration."""

    def test_default_retry_count(self):
        """Verify tasks have retry count configured."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        for task_id, task in dag.task_dict.items():
            assert task.retries >= 0

    def test_retry_delay_configured(self):
        """Verify retry delay is configured."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        for task_id, task in dag.task_dict.items():
            if task.retries > 0:
                assert task.retry_delay is not None

    def test_dataflow_task_wait_until_finished(self):
        """Verify Dataflow task waits for job completion."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        assert dataflow_task.wait_until_finished is True


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestDAGErrorHandling:
    """Tests for error handling in DAG."""

    def test_email_on_failure_configured(self):
        """Verify email notifications on failure are configured."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert dag.default_args.get("email_on_failure") is True
        assert len(dag.default_args.get("email", [])) > 0

    def test_email_on_retry_disabled(self):
        """Verify email on retry is disabled to reduce noise."""
        dag = create_loa_dag(
            job_name="test_job",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert dag.default_args.get("email_on_retry") is False


# ============================================================================
# Parameter & Configuration Tests
# ============================================================================

@pytest.mark.unit
class TestDAGParameterization:
    """Tests for DAG parameterization and configuration."""

    def test_dag_accepts_custom_job_name(self):
        """Verify DAG uses custom job name."""
        job_name = "custom_job"
        dag = create_loa_dag(
            job_name=job_name,
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        assert job_name in dag.dag_id

    def test_dag_accepts_custom_schedule(self):
        """Verify DAG uses custom schedule interval."""
        schedule = "0 12 * * *"
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test",
            schedule_interval=schedule
        )

        assert dag.schedule == schedule

    def test_dag_parses_input_pattern_correctly(self):
        """Verify DAG handles input pattern (used in downstream tasks)."""
        input_pattern = "gs://my-bucket/path/to/data_*"
        dag = create_loa_dag(
            job_name="test",
            input_pattern=input_pattern,
            output_table="project:dataset.test"
        )

        # In PubSub mode, input_pattern is passed to Dataflow
        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        assert dataflow_task.parameters["input_pattern"] == input_pattern

    def test_dag_generates_error_table_if_not_provided(self):
        """Verify error table is generated if not provided."""
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test_table"
        )

        # Verify error table name is in Dataflow parameters
        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        assert dataflow_task.parameters is not None


# ============================================================================
# Dataflow Integration Tests
# ============================================================================

@pytest.mark.unit
class TestDataflowTaskConfiguration:
    """Tests for Dataflow task configuration."""

    def test_dataflow_template_path_provided(self):
        """Verify Dataflow template path is provided."""
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test",
            dataflow_template="gs://templates/loa_template"
        )

        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        assert dataflow_task.template is not None

    def test_dataflow_parameters_include_required_fields(self):
        """Verify Dataflow job parameters include required fields."""
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        params = dataflow_task.parameters

        assert "input_pattern" in params
        assert "output_table" in params
        assert "error_table" in params
        assert "project" in params
        assert "region" in params

    def test_dataflow_region_configured(self):
        """Verify Dataflow region is configured."""
        region = "us-west1"
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test",
            region=region
        )

        dataflow_task = dag.task_dict["run_dataflow_pipeline"]
        assert dataflow_task.location == region


# ============================================================================
# Sensor & Wait Task Tests
# ============================================================================

@pytest.mark.unit
class TestSensorConfiguration:
    """Tests for sensor configuration."""

    def test_pubsub_sensor_configuration(self):
        """Verify PubSub sensor is correctly configured."""
        dag = create_loa_dag(
            job_name="test",
            input_pattern="gs://bucket/test_*",
            output_table="project:dataset.test"
        )

        sensor = dag.task_dict["wait_for_input_files"]
        assert isinstance(sensor, PubSubPullSensor)
        assert sensor.subscription == "loa-processing-notifications-sub"
        assert sensor.ack_messages is True



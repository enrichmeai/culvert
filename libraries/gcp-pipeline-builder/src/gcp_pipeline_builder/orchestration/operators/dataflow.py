"""
Base Dataflow Operator - Unified Processing Interface.

Provides a reusable wrapper around DataflowTemplatedJobStartOperator that:
- Abstracts batch/streaming mode selection
- Abstracts GCS/Pub/Sub source selection
- Provides consistent parameter handling
- Integrates with routing metadata

This is a generic base class that can be extended by specific implementations.

Usage:
    # Direct usage
    operator = BaseDataflowOperator(
        task_id='run_pipeline',
        pipeline_name='my_pipeline',
        source_type='gcs',
        processing_mode='batch',
        input_path='gs://bucket/data/*',
        output_table='project:dataset.table',
    )

    # Extend for project-specific needs
    class MyProjectDataflowOperator(BaseDataflowOperator):
        def __init__(self, task_id, pipeline_name, **kwargs):
            super().__init__(
                task_id=task_id,
                pipeline_name=pipeline_name,
                routing_metadata_key='my_metadata',
                **kwargs
            )
"""

import logging
from typing import Dict, Any, Optional, Literal, List
from dataclasses import dataclass, field
from enum import Enum

from airflow.models import BaseOperator
from airflow.providers.google.cloud.operators.dataflow import (
    DataflowTemplatedJobStartOperator,
    DataflowStartFlexTemplateOperator,
)
from airflow.utils.context import Context

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Data source types for Dataflow jobs."""

    GCS = "gcs"
    PUBSUB = "pubsub"


class ProcessingMode(Enum):
    """Processing modes for Dataflow jobs."""

    BATCH = "batch"
    STREAMING = "streaming"


@dataclass
class DataflowJobConfig:
    """
    Configuration for a Dataflow job.

    Attributes:
        pipeline_name: Name of the pipeline for identification
        source_type: Source type (GCS or Pub/Sub)
        processing_mode: Processing mode (batch or streaming)
        input_path: GCS input path (required for GCS source)
        input_subscription: Pub/Sub subscription (required for Pub/Sub source)
        output_table: BigQuery output table (project:dataset.table)
        error_table: BigQuery error table for failed records
        temp_location: GCS temp location for Dataflow
        template_path: GCS path to Dataflow template
        max_workers: Maximum number of workers
        machine_type: GCE machine type for workers
        additional_params: Additional job parameters
    """

    pipeline_name: str
    source_type: SourceType
    processing_mode: ProcessingMode
    input_path: Optional[str] = None
    input_subscription: Optional[str] = None
    output_table: str = ""
    error_table: Optional[str] = None
    temp_location: str = ""
    template_path: str = ""
    max_workers: int = 10
    machine_type: str = "n1-standard-4"
    additional_params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """
        Validate configuration based on source type.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if self.source_type == SourceType.GCS and not self.input_path:
            errors.append("input_path is required for GCS source")

        if self.source_type == SourceType.PUBSUB and not self.input_subscription:
            errors.append("input_subscription is required for Pub/Sub source")

        if not self.output_table:
            errors.append("output_table is required")

        if not self.pipeline_name:
            errors.append("pipeline_name is required")

        return errors


class BaseDataflowOperator(BaseOperator):
    """
    Base Dataflow operator for data pipelines.

    Wraps DataflowTemplatedJobStartOperator with:
    - Source type abstraction (GCS/Pub/Sub)
    - Processing mode abstraction (Batch/Streaming)
    - Routing metadata integration
    - Consistent error handling

    This is a reusable base class. Extend it for project-specific needs.

    Args:
        task_id: Airflow task ID
        pipeline_name: Name of the pipeline (for job naming)
        source_type: 'gcs' or 'pubsub'
        processing_mode: 'batch' or 'streaming'
        project_id: GCP project ID
        region: GCP region
        input_path: GCS input path (for GCS source)
        input_subscription: Pub/Sub subscription (for Pub/Sub source)
        output_table: BigQuery output table
        error_table: BigQuery error table (optional)
        template_path: GCS path to Dataflow template
        temp_location: GCS temp location
        max_workers: Maximum number of workers
        machine_type: Worker machine type
        routing_metadata_key: XCom key for routing metadata
        job_name_prefix: Prefix for generated job names
        service_account: Service account for Dataflow workers
        network: VPC network for workers
        subnetwork: VPC subnetwork for workers
        additional_params: Additional Dataflow parameters
    """

    template_fields = [
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

    def __init__(
        self,
        task_id: str,
        pipeline_name: str,
        source_type: Literal["gcs", "pubsub"] = "gcs",
        processing_mode: Literal["batch", "streaming"] = "batch",
        project_id: str = "{{ var.value.gcp_project_id }}",
        region: str = "{{ var.value.gcp_region }}",
        input_path: Optional[str] = None,
        input_subscription: Optional[str] = None,
        output_table: str = "",
        error_table: Optional[str] = None,
        template_path: str = "{{ var.value.dataflow_template }}",
        temp_location: str = "{{ var.value.gcp_temp_location }}",
        max_workers: int = 10,
        machine_type: str = "n1-standard-4",
        routing_metadata_key: str = "routing_metadata",
        job_name_prefix: str = "gdw",
        service_account: Optional[str] = None,
        network: Optional[str] = None,
        subnetwork: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(task_id=task_id, **kwargs)
        self.pipeline_name = pipeline_name
        self.source_type = SourceType(source_type)
        self.processing_mode = ProcessingMode(processing_mode)
        self.project_id = project_id
        self.region = region
        self.input_path = input_path
        self.input_subscription = input_subscription
        self.output_table = output_table
        self.error_table = error_table
        self.template_path = template_path
        self.temp_location = temp_location
        self.max_workers = max_workers
        self.machine_type = machine_type
        self.routing_metadata_key = routing_metadata_key
        self.job_name_prefix = job_name_prefix
        self.service_account = service_account
        self.network = network
        self.subnetwork = subnetwork
        self.additional_params = additional_params or {}

    def _validate_configuration(self) -> None:
        """Validate operator configuration."""
        config = DataflowJobConfig(
            pipeline_name=self.pipeline_name,
            source_type=self.source_type,
            processing_mode=self.processing_mode,
            input_path=self.input_path,
            input_subscription=self.input_subscription,
            output_table=self.output_table,
        )
        errors = config.validate()
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

    def _build_parameters(self, context: Context) -> Dict[str, str]:
        """
        Build Dataflow job parameters based on configuration.

        Args:
            context: Airflow task context

        Returns:
            Dictionary of Dataflow job parameters
        """
        params = {
            "outputTable": self.output_table,
            "tempLocation": self.temp_location,
            "maxNumWorkers": str(self.max_workers),
            "workerMachineType": self.machine_type,
        }

        # Add source-specific parameters
        if self.source_type == SourceType.GCS:
            params["inputPath"] = self.input_path
            params["sourceType"] = "gcs"
        elif self.source_type == SourceType.PUBSUB:
            params["inputSubscription"] = self.input_subscription
            params["sourceType"] = "pubsub"

        # Add error table if specified
        if self.error_table:
            params["errorTable"] = self.error_table

        # Add processing mode
        params["processingMode"] = self.processing_mode.value

        # Add service account if specified
        if self.service_account:
            params["serviceAccount"] = self.service_account

        # Try to get routing metadata from XCom
        try:
            ti = context.get("ti") or context.get("task_instance")
            if ti:
                metadata = ti.xcom_pull(key=self.routing_metadata_key)
                if metadata:
                    params["entityType"] = metadata.get("entity_type", "")
                    params["systemId"] = metadata.get("system_id", "")
                    if metadata.get("gcs_path"):
                        params["sourceFilePath"] = metadata.get("gcs_path")
                    logger.info(f"Applied routing metadata: entity_type={metadata.get('entity_type')}")
        except Exception as e:
            logger.warning(f"Could not retrieve routing metadata: {e}")

        # Add any additional parameters
        for key, value in self.additional_params.items():
            params[key] = str(value) if not isinstance(value, str) else value

        return params

    def _get_job_name(self, context: Context) -> str:
        """
        Generate unique job name.

        Args:
            context: Airflow task context

        Returns:
            Unique job name string
        """
        execution_date = context["execution_date"].strftime("%Y%m%d-%H%M%S")
        mode = self.processing_mode.value
        # Job names must match pattern [a-z]([-a-z0-9]*[a-z0-9])?
        job_name = f"{self.job_name_prefix}-{self.pipeline_name}-{mode}-{execution_date}".lower()
        # Replace underscores with hyphens for Dataflow job naming requirements
        job_name = job_name.replace("_", "-")
        return job_name

    def _build_environment_config(self) -> Dict[str, Any]:
        """Build environment configuration for Flex Template jobs."""
        env_config = {
            "maxWorkers": self.max_workers,
            "machineType": self.machine_type,
            "tempLocation": self.temp_location,
        }

        if self.service_account:
            env_config["serviceAccountEmail"] = self.service_account

        if self.network:
            env_config["network"] = self.network

        if self.subnetwork:
            env_config["subnetwork"] = self.subnetwork

        return env_config

    def execute(self, context: Context) -> str:
        """
        Execute the Dataflow job.

        Args:
            context: Airflow task context

        Returns:
            Job ID or result from the Dataflow operator
        """
        # Validate configuration before execution
        self._validate_configuration()

        logger.info(
            f"Starting Dataflow job: pipeline={self.pipeline_name}, "
            f"source={self.source_type.value}, mode={self.processing_mode.value}"
        )

        parameters = self._build_parameters(context)
        job_name = self._get_job_name(context)

        logger.info(f"Generated job name: {job_name}")
        logger.debug(f"Job parameters: {parameters}")

        # Use appropriate operator based on mode
        if self.processing_mode == ProcessingMode.STREAMING:
            # Streaming uses Flex Templates
            result = self._execute_flex_template(context, job_name, parameters)
        else:
            # Batch uses classic templates
            result = self._execute_classic_template(context, job_name, parameters)

        logger.info(f"Dataflow job submitted successfully: {job_name}")
        return result

    def _execute_classic_template(
        self, context: Context, job_name: str, parameters: Dict[str, str]
    ) -> str:
        """Execute using classic Dataflow template."""
        operator = DataflowTemplatedJobStartOperator(
            task_id=f"{self.task_id}_inner",
            project_id=self.project_id,
            location=self.region,
            template=self.template_path,
            job_name=job_name,
            parameters=parameters,
        )
        return operator.execute(context)

    def _execute_flex_template(
        self, context: Context, job_name: str, parameters: Dict[str, str]
    ) -> str:
        """Execute using Flex Template."""
        body = {
            "launchParameter": {
                "jobName": job_name,
                "containerSpecGcsPath": self.template_path,
                "parameters": parameters,
                "environment": self._build_environment_config(),
            }
        }

        operator = DataflowStartFlexTemplateOperator(
            task_id=f"{self.task_id}_inner",
            project_id=self.project_id,
            location=self.region,
            body=body,
        )
        return operator.execute(context)


class BatchDataflowOperator(BaseDataflowOperator):
    """
    Convenience class for batch processing from GCS.

    Pre-configured with:
    - source_type='gcs'
    - processing_mode='batch'

    Args:
        task_id: Airflow task ID
        pipeline_name: Name of the pipeline
        input_path: GCS input path pattern
        output_table: BigQuery output table
        **kwargs: Additional arguments for BaseDataflowOperator
    """

    def __init__(
        self,
        task_id: str,
        pipeline_name: str,
        input_path: str,
        output_table: str,
        **kwargs,
    ):
        # Remove source_type and processing_mode from kwargs if passed
        kwargs.pop("source_type", None)
        kwargs.pop("processing_mode", None)

        super().__init__(
            task_id=task_id,
            pipeline_name=pipeline_name,
            source_type="gcs",
            processing_mode="batch",
            input_path=input_path,
            output_table=output_table,
            **kwargs,
        )


class StreamingDataflowOperator(BaseDataflowOperator):
    """
    Convenience class for streaming processing from Pub/Sub.

    Pre-configured with:
    - source_type='pubsub'
    - processing_mode='streaming'

    Args:
        task_id: Airflow task ID
        pipeline_name: Name of the pipeline
        input_subscription: Pub/Sub subscription path
        output_table: BigQuery output table
        **kwargs: Additional arguments for BaseDataflowOperator
    """

    def __init__(
        self,
        task_id: str,
        pipeline_name: str,
        input_subscription: str,
        output_table: str,
        **kwargs,
    ):
        # Remove source_type and processing_mode from kwargs if passed
        kwargs.pop("source_type", None)
        kwargs.pop("processing_mode", None)

        super().__init__(
            task_id=task_id,
            pipeline_name=pipeline_name,
            source_type="pubsub",
            processing_mode="streaming",
            input_subscription=input_subscription,
            output_table=output_table,
            **kwargs,
        )


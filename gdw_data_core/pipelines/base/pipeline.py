"""
Base Pipeline Module

Abstract base class for GDW migration pipelines with integrated audit,
error handling, and monitoring capabilities.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

from gdw_data_core.core.audit import AuditTrail, AuditPublisher
from gdw_data_core.core.error_handling import ErrorHandler
from gdw_data_core.core.monitoring import MetricsCollector
from gdw_data_core.core import generate_run_id

from .config import PipelineConfig
from .options import GDWPipelineOptions
from . import lifecycle

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """
    Abstract Base Pipeline class for GDW migration jobs.

    Provides a framework for building robust migration pipelines with:
    - Configuration injection
    - Audit trail management for compliance and tracking
    - Error handling with retry logic and error classification
    - Metrics collection and monitoring
    - Lifecycle hooks (on_start, on_success, on_failure)

    Subclasses must implement the `build()` method to define pipeline logic.

    Attributes:
        options: Apache Beam PipelineOptions
        config: PipelineConfig instance with pipeline parameters
        run_id: Unique identifier for this pipeline execution
        audit_manager: AuditTrail instance
        error_handler: ErrorHandler instance
        metrics_emitter: MetricsCollector instance

    Example:
        >>> class MyPipeline(BasePipeline):
        ...     def build(self, pipeline: beam.Pipeline):
        ...         (pipeline
        ...          | 'Read' >> beam.io.ReadFromText('input.txt')
        ...          | 'Process' >> beam.Map(lambda x: x.upper())
        ...          | 'Write' >> beam.io.WriteToText('output.txt'))
        >>>
        >>> options = PipelineOptions()
        >>> config = PipelineConfig(
        ...     run_id='run_001',
        ...     pipeline_name='uppercase_pipeline'
        ... )
        >>> pipeline = MyPipeline(options, config)
        >>> pipeline.run()
    """

    def __init__(
        self,
        options: Optional[PipelineOptions] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base pipeline with configuration and core components.

        Args:
            options: Apache Beam PipelineOptions instance.
                    If not provided, defaults to GDWPipelineOptions()
            config: Configuration dictionary or PipelineConfig instance with keys:
                - run_id: Unique run identifier (required)
                - pipeline_name: Name of pipeline (required)
                - entity_type: Type of entity being processed (default: 'data')
                - source_file: Input source file/path (default: 'unknown')
                - gcp_project_id: GCP project ID (optional)
                - bigquery_dataset: BigQuery dataset name (optional)

        Raises:
            ValueError: If configuration validation fails

        Example:
            >>> config = PipelineConfig(
            ...     run_id='run_20231225_001',
            ...     pipeline_name='loa_applications_migration'
            ... )
            >>> options = GDWPipelineOptions(['--num_workers=2'])
            >>> pipeline = BasePipeline(options, config)
        """
        self.options = options or GDWPipelineOptions()

        # Handle both dict and PipelineConfig inputs
        if isinstance(config, PipelineConfig):
            self.config = config
            self._config_dict = config.to_dict()
        elif isinstance(config, dict):
            self.config = PipelineConfig(**config) if 'run_id' in config else None
            self._config_dict = config or {}
        else:
            self.config = None
            self._config_dict = {}

        # Generate run ID if not provided
        pipeline_name = self._config_dict.get('pipeline_name', 'pipeline')
        self.run_id = self._config_dict.get('run_id', generate_run_id(pipeline_name))

        # Validate config if provided
        if self.config:
            self.config.validate()

        # Initialize core components
        self._init_audit_manager()
        self._init_error_handler()
        self._init_metrics_emitter()

        logger.info(
            f"BasePipeline initialized: run_id={self.run_id}, "
            f"pipeline={self._config_dict.get('pipeline_name')}"
        )

    def _init_audit_manager(self) -> None:
        """
        Initialize audit trail manager.

        Creates an AuditTrail instance for recording pipeline events
        for compliance, tracking, and debugging purposes.
        """
        publisher = None
        project_id = self._config_dict.get('project_id') or self._config_dict.get('gcp_project_id')
        audit_topic = self._config_dict.get('audit_topic')
        
        if project_id and audit_topic:
            try:
                publisher = AuditPublisher(project_id=project_id, topic_name=audit_topic)
                logger.debug(f"Audit publisher initialized for topic: {audit_topic}")
            except Exception as e:
                logger.warning(f"Failed to initialize audit publisher: {e}")

        self.audit_manager = AuditTrail(
            run_id=self.run_id,
            pipeline_name=self._config_dict.get('pipeline_name', 'unknown'),
            entity_type=self._config_dict.get('entity_type', 'data'),
            publisher=publisher
        )
        # Initialize source_file to avoid AttributeError later
        self.audit_manager.source_file = self._config_dict.get('source_file', 'unknown')
        logger.debug("Audit manager initialized")

    def _init_error_handler(self) -> None:
        """
        Initialize error handler.

        Creates an ErrorHandler instance for classifying, handling,
        and recording errors that occur during pipeline execution.
        """
        self.error_handler = ErrorHandler(
            pipeline_name=self._config_dict.get('pipeline_name', 'unknown'),
            run_id=self.run_id
        )
        logger.debug("Error handler initialized")

    def _init_metrics_emitter(self) -> None:
        """
        Initialize metrics collector.

        Creates a MetricsCollector instance for tracking metrics
        and performance data during pipeline execution.
        """
        self.metrics_emitter = MetricsCollector(
            pipeline_name=self._config_dict.get('pipeline_name', 'unknown'),
            run_id=self.run_id
        )
        logger.debug("Metrics emitter initialized")

    @abstractmethod
    def build(self, pipeline: beam.Pipeline) -> None:
        """
        Build the pipeline logic.

        Subclasses must override this method to define the actual
        pipeline steps including transforms, I/O operations, and branching.

        This method is called within the pipeline execution context
        and should use the provided Pipeline instance to construct
        the pipeline DAG.

        Args:
            pipeline: Apache Beam Pipeline instance to add transforms to

        Example:
            >>> def build(self, pipeline: beam.Pipeline):
            ...     (pipeline
            ...      | 'ReadText' >> beam.io.ReadFromText('input.txt')
            ...      | 'ProcessData' >> beam.Map(self._process)
            ...      | 'WriteOutput' >> beam.io.WriteToText('output.txt'))
        """
        pass

    def run(self) -> None:
        """
        Execute the pipeline with error handling and auditing.

        Manages the complete pipeline lifecycle:
        1. Calls on_start() to initialize audit and metrics
        2. Executes build() to run pipeline logic
        3. Calls on_success() to record success and metrics
        4. Calls on_failure() if exception occurs

        Lifecycle flow:
            try:
                on_start()
                build()
                on_success()
            except Exception:
                on_failure(exception)
                raise

        Raises:
            Exception: Re-raises any exception that occurred during execution
                      after calling on_failure() hook

        Example:
            >>> pipeline = MyPipeline(options, config)
            >>> try:
            ...     pipeline.run()
            ... except Exception as e:
            ...     print(f"Pipeline failed: {e}")
        """
        try:
            logger.info(f"Starting pipeline execution: {self.run_id}")

            # Call start hook
            lifecycle.on_start(
                self.audit_manager,
                self.metrics_emitter,
                self._config_dict,
                self.run_id
            )

            # Execute pipeline
            with beam.Pipeline(options=self.options) as p:
                self.build(p)

            # Call success hook
            lifecycle.on_success(
                self.audit_manager,
                self.metrics_emitter,
                self.run_id
            )

            logger.info(f"Pipeline execution completed successfully: {self.run_id}")

        except Exception as e:
            # Call failure hook
            lifecycle.on_failure(
                e,
                self.audit_manager,
                self.error_handler,
                self.metrics_emitter,
                self._config_dict,
                self.run_id
            )

            # Re-raise exception
            raise

    def get_audit_record(self) -> Dict[str, Any]:
        """
        Get the audit record for this pipeline execution.

        Returns audit trail data recorded during pipeline execution
        for compliance and tracking purposes.

        Returns:
            Dictionary containing audit trail information

        Example:
            >>> pipeline = MyPipeline(options, config)
            >>> pipeline.run()
            >>> audit_record = pipeline.get_audit_record()
            >>> print(audit_record)
        """
        return self.audit_manager.get_audit_record()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of metrics collected during pipeline execution.

        Returns:
            Dictionary containing metrics statistics and performance data

        Example:
            >>> metrics = pipeline.get_metrics_summary()
            >>> print(f"Total records processed: {metrics['records_processed']}")
        """
        return self.metrics_emitter.get_statistics()

    def get_error_count(self) -> int:
        """
        Get total error count from pipeline execution.

        Returns:
            Number of errors that occurred during pipeline execution

        Example:
            >>> error_count = pipeline.get_error_count()
            >>> if error_count > 0:
            ...     print(f"Pipeline had {error_count} errors")
        """
        return len(self.error_handler.errors)


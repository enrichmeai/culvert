"""
Pipeline Builder Module

Helper class for constructing Apache Beam migration pipelines.
"""

import logging
from typing import List, Callable, Dict, Any, Optional

import apache_beam as beam

from .transforms import (
    ParseCsvLine, ValidateRecordDoFn, TransformRecordDoFn
)
from .io import ReadCSVFromGCSDoFn, BatchWriteToBigQueryDoFn

logger = logging.getLogger(__name__)


class BeamPipelineBuilder:
    """
    Helper class for building migration pipelines with common patterns.

    Provides a fluent interface for constructing pipelines with common
    transformation and I/O patterns. Simplifies pipeline construction
    for standard migration workflows.

    Attributes:
        pipeline_name: Name of the pipeline
        run_id: Unique pipeline run identifier
        pipeline: The Beam Pipeline instance
        current_pcoll: Current PCollection being built

    Example:
        >>> builder = BeamPipelineBuilder('migration_job', 'run_123')
        >>> result = builder.read_csv(['gs://bucket/input.csv']) \
        ...                 .validate(validate_fn) \
        ...                 .transform(transform_fn) \
        ...                 .write_to_bigquery('dataset', 'table') \
        ...                 .run()
    """

    def __init__(self, pipeline_name: str, run_id: str):
        """
        Initialize pipeline builder.

        Args:
            pipeline_name: Name of the pipeline for tracking
            run_id: Unique identifier for this run

        Example:
            >>> builder = BeamPipelineBuilder('my_pipeline', 'run_001')
        """
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.pipeline = beam.Pipeline()
        self.current_pcoll = None
        logger.info(f"Pipeline builder initialized: {pipeline_name}")

    def read_csv(self, gcs_paths: List[str], field_names: Optional[List[str]] = None) -> 'BeamPipelineBuilder':
        """
        Read CSV files from GCS.

        Args:
            gcs_paths: List of GCS paths to CSV files
            field_names: Optional list of field names. If not provided,
                        uses first row as header

        Returns:
            BeamPipelineBuilder: For method chaining

        Example:
            >>> builder.read_csv(['gs://bucket/input.csv'])
        """
        logger.info(f"Reading CSV from {len(gcs_paths)} file(s)")

        if field_names:
            self.current_pcoll = (
                self.pipeline
                | 'CreatePaths' >> beam.Create(gcs_paths)
                | 'ReadCSV' >> beam.ParDo(ReadCSVFromGCSDoFn())
            )
        else:
            self.current_pcoll = (
                self.pipeline
                | 'CreatePaths' >> beam.Create(gcs_paths)
                | 'ReadCSV' >> beam.ParDo(ReadCSVFromGCSDoFn())
            )

        return self

    def validate(self, validation_fn: Callable) -> 'BeamPipelineBuilder':
        """
        Validate records with custom validation function.

        Args:
            validation_fn: Function that returns list of errors (empty if valid)

        Returns:
            BeamPipelineBuilder: For method chaining

        Example:
            >>> def validate_record(record):
            ...     errors = []
            ...     if not record.get('id'):
            ...         errors.append('Missing id')
            ...     return errors
            >>>
            >>> builder.validate(validate_record)
        """
        logger.info("Adding validation step")

        validated = self.current_pcoll | 'Validate' >> beam.ParDo(
            ValidateRecordDoFn(validation_fn)
        ).with_outputs('main', 'invalid')

        self.current_pcoll = validated['main']

        return self

    def transform(self, transform_fn: Callable) -> 'BeamPipelineBuilder':
        """
        Transform records with custom transformation function.

        Args:
            transform_fn: Function that takes a record and returns transformed record

        Returns:
            BeamPipelineBuilder: For method chaining

        Example:
            >>> def add_timestamp(record):
            ...     from datetime import datetime
            ...     return {**record, 'timestamp': datetime.now().isoformat()}
            >>>
            >>> builder.transform(add_timestamp)
        """
        logger.info("Adding transform step")

        self.current_pcoll = (
            self.current_pcoll
            | 'Transform' >> beam.ParDo(TransformRecordDoFn(transform_fn))
        )

        return self

    def write_to_bigquery(
        self,
        dataset: str,
        table: str,
        batch_size: int = 1000
    ) -> 'BeamPipelineBuilder':
        """
        Write records to BigQuery.

        Args:
            dataset: BigQuery dataset name
            table: BigQuery table name
            batch_size: Records per batch (default: 1000)

        Returns:
            BeamPipelineBuilder: For method chaining

        Example:
            >>> builder.write_to_bigquery('my_dataset', 'my_table')
        """
        logger.info(f"Adding BigQuery write step: {dataset}.{table}")

        self.current_pcoll = (
            self.current_pcoll
            | 'WriteBQ' >> beam.ParDo(
                BatchWriteToBigQueryDoFn(
                    project=self._get_project(),
                    dataset=dataset,
                    table=table,
                    batch_size=batch_size
                )
            )
        )

        return self

    def run(self) -> Any:
        """
        Run the pipeline.

        Executes the constructed pipeline and waits for completion.

        Returns:
            Pipeline result object

        Example:
            >>> result = builder.run()
            >>> result.wait_until_finish()
        """
        logger.info(f"Running pipeline: {self.pipeline_name}")
        return self.pipeline.run()

    @staticmethod
    def _get_project() -> str:
        """
        Get GCP project ID from environment or default.

        Returns:
            str: GCP project ID
        """
        try:
            from google.cloud import bigquery
            return bigquery.Client().project
        except Exception as e:
            logger.warning(f"Could not determine GCP project: {e}")
            return "unknown"


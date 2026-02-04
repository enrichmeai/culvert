"""
Pipelines Module - Apache Beam Pipeline Framework

Complete pipeline framework with base classes, configuration, and reusable
transforms and I/O operations for GDW migration jobs.

This module provides everything needed to build, configure, and execute
robust Apache Beam migration pipelines with integrated audit trail,
error handling, and metrics collection.

Core Components:
    BasePipeline: Abstract base class for all pipelines
    PipelineConfig: Configuration dataclass
    GDWPipelineOptions: Command-line options

Transforms:
    ParseCsvLine: Parse CSV lines
    ValidateRecordDoFn: Validate records
    FilterRecordsDoFn: Filter records
    TransformRecordDoFn: Transform records
    EnrichWithMetadataDoFn: Add metadata
    DeduplicateRecordsDoFn: Remove duplicates

I/O Operations:
    ReadFromGCSDoFn: Read from GCS
    WriteToGCSDoFn: Write to GCS
    ReadCSVFromGCSDoFn: Read CSV from GCS
    WriteCSVToGCSDoFn: Write CSV to GCS
    WriteToBigQueryDoFn: Write to BigQuery
    BatchWriteToBigQueryDoFn: Batch write to BigQuery

Advanced Features:
    PublishToPubSubDoFn: Publish to Pub/Sub
    BeamPipelineBuilder: Fluent pipeline construction

Example:
    >>> from gcp_pipeline_beam.pipelines import BasePipeline, PipelineConfig
    >>> from gcp_pipeline_beam.pipelines import ParseCsvLine, ValidateRecordDoFn
    >>>
    >>> class MyPipeline(BasePipeline):
    ...     def build(self, pipeline):
    ...         (pipeline
    ...          | 'Read' >> beam.io.ReadFromText('input.csv')
    ...          | 'Parse' >> beam.ParDo(ParseCsvLine(['id', 'name']))
    ...          | 'Validate' >> beam.ParDo(ValidateRecordDoFn(validate_fn))
    ...          | 'Write' >> beam.io.WriteToText('output.txt'))
    >>>
    >>> config = PipelineConfig(
    ...     run_id='run_001',
    ...     pipeline_name='my_pipeline'
    ... )
    >>> pipeline = MyPipeline(config=config)
    >>> pipeline.run()
"""

from .base import (
    BasePipeline,
    PipelineConfig,
    GDWPipelineOptions,
)

from .beam import (
    # Transforms
    ParseCsvLine,
    ValidateRecordDoFn,
    FilterRecordsDoFn,
    TransformRecordDoFn,
    EnrichWithMetadataDoFn,
    DeduplicateRecordsDoFn,
    # I/O
    ReadFromGCSDoFn,
    WriteToGCSDoFn,
    ReadCSVFromGCSDoFn,
    WriteCSVToGCSDoFn,
    WriteToBigQueryDoFn,
    BatchWriteToBigQueryDoFn,
    # PubSub
    PublishToPubSubDoFn,
    # Builder
    BeamPipelineBuilder,
)

__all__ = [
    # Base Pipeline Framework
    'BasePipeline',
    'PipelineConfig',
    'GDWPipelineOptions',
    # Transforms
    'ParseCsvLine',
    'ValidateRecordDoFn',
    'FilterRecordsDoFn',
    'TransformRecordDoFn',
    'EnrichWithMetadataDoFn',
    'DeduplicateRecordsDoFn',
    # I/O
    'ReadFromGCSDoFn',
    'WriteToGCSDoFn',
    'ReadCSVFromGCSDoFn',
    'WriteCSVToGCSDoFn',
    'WriteToBigQueryDoFn',
    'BatchWriteToBigQueryDoFn',
    # PubSub
    'PublishToPubSubDoFn',
    # Builder
    'BeamPipelineBuilder',
]


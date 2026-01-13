"""
Beam Transforms and I/O Package

Complete Apache Beam framework with DoFn transforms and I/O operations
for building robust migration pipelines.

This package consolidates all Beam transforms, I/O operations, and
utilities for pipeline construction.

Exports:
    Transforms:
        ParseCsvLine: Parse CSV lines into records
        ValidateRecordDoFn: Validate records
        FilterRecordsDoFn: Filter records by predicate
        TransformRecordDoFn: Transform records
        EnrichWithMetadataDoFn: Add metadata to records
        DeduplicateRecordsDoFn: Remove duplicates

    I/O:
        ReadFromGCSDoFn: Read from GCS
        WriteToGCSDoFn: Write to GCS
        ReadCSVFromGCSDoFn: Read CSV from GCS
        WriteCSVToGCSDoFn: Write CSV to GCS
        WriteToBigQueryDoFn: Write to BigQuery
        BatchWriteToBigQueryDoFn: Batch write to BigQuery

    PubSub:
        PublishToPubSubDoFn: Publish to Pub/Sub

    Builder:
        BeamPipelineBuilder: Fluent pipeline construction

Example:
    >>> from gcp_pipeline_beam.pipelines.beam import (
    ...     ParseCsvLine, ValidateRecordDoFn, BeamPipelineBuilder
    ... )
    >>>
    >>> builder = BeamPipelineBuilder('my_pipeline', 'run_001')
    >>> result = builder.read_csv(['gs://bucket/input.csv'])\\
    ...                 .validate(validate_fn)\\
    ...                 .write_to_bigquery('dataset', 'table')\\
    ...                 .run()
"""

from .transforms import (
    ParseCsvLine,
    ValidateRecordDoFn,
    FilterRecordsDoFn,
    TransformRecordDoFn,
    EnrichWithMetadataDoFn,
    DeduplicateRecordsDoFn,
)

from .io import (
    ReadFromGCSDoFn,
    WriteToGCSDoFn,
    ReadCSVFromGCSDoFn,
    WriteCSVToGCSDoFn,
    WriteToBigQueryDoFn,
    BatchWriteToBigQueryDoFn,
)

from .pubsub import PublishToPubSubDoFn
from .builder import BeamPipelineBuilder

__all__ = [
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


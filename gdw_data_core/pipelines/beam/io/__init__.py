"""
Beam I/O Operations Package

DoFn classes for reading from and writing to external systems
in Apache Beam pipelines, including GCS and BigQuery.

This package provides reusable I/O components for cloud-native
data pipelines with proper error handling and metrics.

Exports:
    ReadFromGCSDoFn: Read text files from Google Cloud Storage
    WriteToGCSDoFn: Write text files to Google Cloud Storage
    ReadCSVFromGCSDoFn: Read CSV files from GCS into dictionaries
    WriteCSVToGCSDoFn: Write dictionaries to GCS as CSV
    WriteToBigQueryDoFn: Write records to BigQuery (one at a time)
    BatchWriteToBigQueryDoFn: Write records to BigQuery in batches

Example:
    >>> from gdw_data_core.pipelines.beam.io import (
    ...     ReadFromGCSDoFn, WriteToBigQueryDoFn
    ... )
    >>>
    >>> pipeline | 'ReadGCS' >> beam.Create(['gs://bucket/input.txt'])
    ...         | 'Read' >> beam.ParDo(ReadFromGCSDoFn())
    ...         | 'WriteBQ' >> beam.ParDo(WriteToBigQueryDoFn(
    ...             project='my-project',
    ...             dataset='dataset',
    ...             table='table'
    ...         ))
"""

from .gcs import (
    ReadFromGCSDoFn,
    WriteToGCSDoFn,
    ReadCSVFromGCSDoFn,
    WriteCSVToGCSDoFn,
)
from .bigquery import (
    WriteToBigQueryDoFn,
    BatchWriteToBigQueryDoFn,
)

__all__ = [
    'ReadFromGCSDoFn',
    'WriteToGCSDoFn',
    'ReadCSVFromGCSDoFn',
    'WriteCSVToGCSDoFn',
    'WriteToBigQueryDoFn',
    'BatchWriteToBigQueryDoFn',
]


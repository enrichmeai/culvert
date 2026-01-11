"""
Beam Data Transformations Package

DoFn transforms for data parsing, validation, filtering, and enrichment
in Apache Beam pipelines.

This package provides reusable, focused DoFn classes for common data
transformation patterns in migration pipelines.

Exports:
    ParseCsvLine: Parse CSV lines into record dictionaries
    ValidateRecordDoFn: Validate records with custom function or schema
    SchemaValidateRecordDoFn: Schema-driven record validation
    FilterRecordsDoFn: Filter records based on predicates
    TransformRecordDoFn: Transform records with custom function
    EnrichWithMetadataDoFn: Add pipeline metadata to records
    DeduplicateRecordsDoFn: Remove duplicate records by key

Example (Schema-driven validation):
    >>> from gcp_pipeline_beam.pipelines.beam.transforms import (
    ...     ParseCsvLine, SchemaValidateRecordDoFn
    ... )
    >>> from em.schema import EMCustomerSchema
    >>>
    >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
    ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(EMCustomerSchema.get_csv_headers()))
    ...         | 'Validate' >> beam.ParDo(SchemaValidateRecordDoFn(EMCustomerSchema))
"""

from .parsers import ParseCsvLine
from .pii import MaskPIIDoFn
from .validators import ValidateRecordDoFn, SchemaValidateRecordDoFn
from .filters import FilterRecordsDoFn
from .transformers import TransformRecordDoFn
from .enrichers import EnrichWithMetadataDoFn
from .deduplicators import DeduplicateRecordsDoFn

__all__ = [
    'ParseCsvLine',
    'MaskPIIDoFn',
    'ValidateRecordDoFn',
    'SchemaValidateRecordDoFn',
    'FilterRecordsDoFn',
    'TransformRecordDoFn',
    'EnrichWithMetadataDoFn',
    'DeduplicateRecordsDoFn',
]


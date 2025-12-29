"""
Beam Data Transformations Package

DoFn transforms for data parsing, validation, filtering, and enrichment
in Apache Beam pipelines.

This package provides reusable, focused DoFn classes for common data
transformation patterns in migration pipelines.

Exports:
    ParseCsvLine: Parse CSV lines into record dictionaries
    ValidateRecordDoFn: Validate records with custom validation function
    FilterRecordsDoFn: Filter records based on predicates
    TransformRecordDoFn: Transform records with custom function
    EnrichWithMetadataDoFn: Add pipeline metadata to records
    DeduplicateRecordsDoFn: Remove duplicate records by key

Example:
    >>> from gdw_data_core.pipelines.beam.transforms import (
    ...     ParseCsvLine, ValidateRecordDoFn, FilterRecordsDoFn
    ... )
    >>>
    >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
    ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'name']))
    ...         | 'Validate' >> beam.ParDo(ValidateRecordDoFn(validate_fn))
    ...         | 'Filter' >> beam.ParDo(FilterRecordsDoFn(filter_fn))
"""

from .parsers import ParseCsvLine
from .validators import ValidateRecordDoFn
from .filters import FilterRecordsDoFn
from .transformers import TransformRecordDoFn
from .enrichers import EnrichWithMetadataDoFn
from .deduplicators import DeduplicateRecordsDoFn

__all__ = [
    'ParseCsvLine',
    'ValidateRecordDoFn',
    'FilterRecordsDoFn',
    'TransformRecordDoFn',
    'EnrichWithMetadataDoFn',
    'DeduplicateRecordsDoFn',
]


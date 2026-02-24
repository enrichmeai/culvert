"""
Generic Pipeline Module.

Apache Beam pipelines for Generic entity processing.
Uses gcp_pipeline_core library components with schema-driven validation.
"""

from .options import EMPipelineOptions
from .transforms import (
    ValidateFileDoFn,
    ParseAndValidateRecordDoFn,
    AddAuditColumnsDoFn,
)
from .runner import run_pipeline
from .ingestion_pipeline import (
    AddAuditColumnsDoFn as EMAddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
    run_ingestion_pipeline,
)

# Schema-driven validation from library
from gcp_pipeline_beam.pipelines.beam.transforms import SchemaValidateRecordDoFn

__all__ = [
    # Legacy/shared
    'EMPipelineOptions',
    'ValidateFileDoFn',
    'ParseAndValidateRecordDoFn',
    'AddAuditColumnsDoFn',
    'run_pipeline',
    # Generic-specific
    'EMAddAuditColumnsDoFn',
    'EM_ENTITY_CONFIG',
    'run_ingestion_pipeline',
    # Schema-driven validation (from library)
    'SchemaValidateRecordDoFn',
]

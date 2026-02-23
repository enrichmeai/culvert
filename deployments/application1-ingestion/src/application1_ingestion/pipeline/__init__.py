"""
Application1 Pipeline Module.

Apache Beam pipelines for Application1 entity processing.
Uses gcp_pipeline_core library components with schema-driven validation.
"""

from .options import EMPipelineOptions
from .transforms import (
    ValidateFileDoFn,
    ParseAndValidateRecordDoFn,
    AddAuditColumnsDoFn,
)
from .runner import run_pipeline
from .application1_pipeline import (
    AddAuditColumnsDoFn as EMAddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
    run_application1_pipeline,
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
    # Application1-specific
    'EMAddAuditColumnsDoFn',
    'EM_ENTITY_CONFIG',
    'run_application1_pipeline',
    # Schema-driven validation (from library)
    'SchemaValidateRecordDoFn',
]

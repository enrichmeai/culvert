"""
EM Pipeline Module.

Apache Beam pipelines for EM entity processing.
Uses gcp_pipeline_core library components with schema-driven validation.
"""

from .options import EMPipelineOptions
from .transforms import (
    ValidateFileDoFn,
    ParseAndValidateRecordDoFn,
    AddAuditColumnsDoFn,
)
from .runner import run_pipeline
from .em_pipeline import (
    AddAuditColumnsDoFn as EMAddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
    run_em_pipeline,
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
    # EM-specific
    'EMAddAuditColumnsDoFn',
    'EM_ENTITY_CONFIG',
    'run_em_pipeline',
    # Schema-driven validation (from library)
    'SchemaValidateRecordDoFn',
]

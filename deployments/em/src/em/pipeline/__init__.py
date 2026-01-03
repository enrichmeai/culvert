"""
EM Pipeline Module.

Apache Beam pipelines for EM entity processing.
Uses gcp_pipeline_builder library components.
"""

from .options import EMPipelineOptions
from .transforms import (
    ValidateFileDoFn,
    ParseAndValidateRecordDoFn,
    AddAuditColumnsDoFn,
)
from .runner import run_pipeline
from .em_pipeline import (
    ValidateEMRecordDoFn,
    AddAuditColumnsDoFn as EMAddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
    run_em_pipeline,
)

__all__ = [
    # Legacy/shared
    'EMPipelineOptions',
    'ValidateFileDoFn',
    'ParseAndValidateRecordDoFn',
    'AddAuditColumnsDoFn',
    'run_pipeline',
    # EM-specific
    'ValidateEMRecordDoFn',
    'EMAddAuditColumnsDoFn',
    'EM_ENTITY_CONFIG',
    'run_em_pipeline',
]

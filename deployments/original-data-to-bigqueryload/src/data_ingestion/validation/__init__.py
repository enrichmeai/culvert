"""
Generic Validation Module.

Provides validation for Generic entities using gcp_pipeline_core library.
"""

from .types import ValidationResult
from .file_validator import GenericFileValidator
from .record_validator import GenericRecordValidator
from .validator import GenericValidator

__all__ = [
    'ValidationResult',
    'GenericFileValidator',
    'GenericRecordValidator',
    'GenericValidator',
]


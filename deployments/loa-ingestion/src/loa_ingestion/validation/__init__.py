"""
LOA Validation Module.

Provides validation for LOA entities using gcp_pipeline_builder library.

Components:
- ValidationResult: Data type for validation results
- LOAFileValidator: HDR/TRL and file structure validation
- LOARecordValidator: Field-level record validation
- LOAValidator: Unified validator combining both

Example:
    >>> from loa_ingestion.validation import LOAValidator
    >>> validator = LOAValidator()
    >>> result = validator.validate_file(file_lines, "applications")
    >>> if result.is_valid:
    ...     valid, errors = validator.validate_records(records, "applications")
"""

from .types import ValidationResult
from .file_validator import LOAFileValidator
from .record_validator import LOARecordValidator
from .validator import LOAValidator

__all__ = [
    'ValidationResult',
    'LOAFileValidator',
    'LOARecordValidator',
    'LOAValidator',
]


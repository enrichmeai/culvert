"""
GCP Pipeline Framework - Validators
Core validators with PII masking and structured error reporting.
"""

from .types import ValidationError
from .numeric import validate_numeric_range
from .date import validate_date
from .code import validate_branch_code, validate_entity_code
from .generic import validate_required, validate_length
from .schema_validator import SchemaValidator
from .classes import (
    ValidationResult,
    BaseValidator,
    RequiredValidator,
    RegexValidator,
    DateValidator,
    NumericValidator,
    SSNValidator,
    PostcodeValidator,
    CompositeValidator,
)

__all__ = [
    # Function-style API (original)
    'ValidationError',
    'SchemaValidator',
    'validate_numeric_range',
    'validate_date',
    'validate_branch_code',
    'validate_entity_code',
    'validate_required',
    'validate_length',
    # Class-style, composable API (referenced by the book)
    'ValidationResult',
    'BaseValidator',
    'RequiredValidator',
    'RegexValidator',
    'DateValidator',
    'NumericValidator',
    'SSNValidator',
    'PostcodeValidator',
    'CompositeValidator',
]


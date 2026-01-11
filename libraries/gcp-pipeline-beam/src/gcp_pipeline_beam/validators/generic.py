"""
Generic/utility validators.
"""

from typing import List, Any

from .types import ValidationError


def validate_required(field: str, value: Any) -> List[ValidationError]:
    """
    Validate that a field is required and not empty.

    Args:
        field: Name of the field being validated
        value: Value to check

    Returns:
        List of ValidationError objects if validation fails
    """
    errors = []
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(ValidationError(field, str(value), f"{field} is required"))
    return errors


def validate_length(
    field: str,
    value: str,
    min_length: int = 0,
    max_length: int = None
) -> List[ValidationError]:
    """
    Validate string length.

    Args:
        field: Name of the field being validated
        value: String value to check
        min_length: Minimum allowed length
        max_length: Maximum allowed length (optional)

    Returns:
        List of ValidationError objects if validation fails
    """
    errors = []
    if not value:
        return errors

    if len(value) < min_length:
        errors.append(ValidationError(field, value, f"{field} must be at least {min_length} characters"))

    if max_length and len(value) > max_length:
        errors.append(ValidationError(field, value, f"{field} must be at most {max_length} characters"))

    return errors


"""
Numeric validation logic.
"""

from typing import List, Tuple, Optional

from .types import ValidationError


def validate_numeric_range(field: str, value_str: str, min_val: float, max_val: float) -> Tuple[Optional[float], List[ValidationError]]:
    """Generic numeric range validator."""
    errors = []
    if not value_str:
        errors.append(ValidationError(field, value_str, f"{field} is required"))
        return None, errors

    clean_val = str(value_str).replace("$", "").replace(",", "")
    try:
        val = float(clean_val)
    except ValueError:
        errors.append(ValidationError(field, value_str, f"{field} must be numeric (got: {value_str})"))
        return None, errors

    if val < min_val:
        errors.append(ValidationError(field, str(val), f"{field} must be >= {min_val}"))
    if val > max_val:
        errors.append(ValidationError(field, str(val), f"{field} must be <= {max_val}"))

    return val if not errors else None, errors

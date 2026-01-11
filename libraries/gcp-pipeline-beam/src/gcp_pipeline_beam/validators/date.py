"""
Date validation logic.
"""

from datetime import datetime
from typing import List, Tuple, Optional

from .types import ValidationError


def validate_date(field: str, date_str: str, fmt: str = "%Y-%m-%d", allow_future: bool = False, max_age_years: Optional[int] = None) -> Tuple[Optional[str], List[ValidationError]]:
    """Generic date validator."""
    errors = []
    if not date_str:
        errors.append(ValidationError(field, date_str, f"{field} is required"))
        return None, errors

    try:
        date_obj = datetime.strptime(date_str, fmt)
    except ValueError:
        errors.append(ValidationError(field, date_str, f"{field} must be in format {fmt} (got: {date_str})"))
        return None, errors

    if not allow_future and date_obj > datetime.now():
        errors.append(ValidationError(field, date_str, f"{field} cannot be in the future"))

    if max_age_years:
        min_date = datetime.now().replace(year=datetime.now().year - max_age_years)
        if date_obj < min_date:
            errors.append(ValidationError(field, date_str, f"{field} cannot be more than {max_age_years} years old"))

    return date_str if not errors else None, errors

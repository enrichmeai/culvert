"""
Code validation logic (branch codes, entity codes, etc).
"""

import re
from typing import List

from .types import ValidationError


def validate_branch_code(branch_code: str) -> List[ValidationError]:
    """Validate branch code format."""
    errors = []
    if not branch_code:
        errors.append(ValidationError("branch_code", branch_code, "Branch code is required"))
        return errors

    if not re.match(r'^[A-Z]{1,2}\d{4,6}$', branch_code.upper()):
        errors.append(ValidationError("branch_code", branch_code, "Branch code must be 6-8 alphanumeric chars (e.g., NY1234)"))

    return errors


def validate_entity_code(entity_code: str) -> List[ValidationError]:
    """Validate entity code format."""
    errors = []
    if not entity_code:
        errors.append(ValidationError("entity_code", entity_code, "Entity code is required"))
        return errors

    # Entity codes are typically alphanumeric, 3-10 characters
    if not re.match(r'^[A-Z0-9]{3,10}$', entity_code.upper()):
        errors.append(ValidationError("entity_code", entity_code, "Entity code must be 3-10 alphanumeric characters"))

    return errors


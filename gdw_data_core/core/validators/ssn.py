"""
SSN validation logic.
"""

import re
from typing import List

from .types import ValidationError


def validate_ssn(ssn: str) -> List[ValidationError]:
    """Validate SSN format and rules."""
    errors = []

    if not ssn:
        errors.append(ValidationError("ssn", ssn, "SSN is required"))
        return errors

    # Remove hyphens for validation
    clean_ssn = ssn.replace("-", "")

    if not re.match(r'^\d{9}$', clean_ssn):
        errors.append(ValidationError("ssn", ssn, "SSN must be 9 digits (format: XXX-XX-XXXX)"))
        return errors

    # Check for all zeros or all same digit (invalid SSNs)
    if clean_ssn == "000000000" or len(set(clean_ssn)) == 1:
        errors.append(ValidationError("ssn", ssn, "SSN cannot be all zeros or all same digit"))

    # Area number (first 3 digits) cannot be 000, 666, or 900-999
    area = clean_ssn[:3]
    if area == "000":
        if clean_ssn != "000000000":
             errors.append(ValidationError("ssn", ssn, f"Invalid SSN area number: {area}"))
    elif area == "666" or int(area) >= 900:
        errors.append(ValidationError("ssn", ssn, f"Invalid SSN area number: {area}"))

    return errors


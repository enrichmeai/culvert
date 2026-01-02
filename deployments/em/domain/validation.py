"""
Validation Module - LOA Blueprint

Demonstrates proper usage of GDW Data Core validators.

Example:
    from gdw_data_core.core.validators import ValidationError
    from blueprint.components.loa_domain.validation import validate_application_record

    record = {'ssn': '123-45-6789', 'loan_amount': '50000', ...}
    validated, errors = validate_application_record(record)

    if errors:
        for error in errors:
            print(f"Field {error.field}: {error.message}")
            # PII automatically masked in error.value
"""

from typing import List, Tuple, Optional, Any, Dict
from gdw_data_core.core.validators import (
    ValidationError,
    validate_ssn,
    validate_numeric_range,
    validate_date,
    validate_branch_code as core_validate_branch_code
)

def validate_loan_amount(
        amount_str: str,
        min_val: int = 1,
        max_val: int = 1_000_000) -> Tuple[
    Optional[int], List[ValidationError]]:
    """
    Validate loan amount using core numeric range validator.

    Args:
        amount_str: Amount as string (can include commas, $)
        min_val: Minimum allowed amount
        max_val: Maximum allowed amount

    Returns:
        Tuple of (validated_amount, errors)

    Example:
        >>> amount, errors = validate_loan_amount("$50,000")
        >>> if not errors:
        ...     print(f"Valid amount: ${amount:,}")
    """
    val, errors = validate_numeric_range(
        "loan_amount", amount_str, min_val, max_val)
    return int(val) if val is not None else None, errors

def validate_loan_type(loan_type: str) -> List[ValidationError]:
    """Validate loan type against allowed values."""
    # This remains implementation specific but uses the core ValidationError
    errors = []
    allowed_types = {"MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"}
    if not loan_type:
        errors.append(
            ValidationError("loan_type", loan_type,
                          "Loan type is required"))
        return errors
    loan_type_upper = loan_type.upper()
    if loan_type_upper not in allowed_types:
        errors.append(ValidationError(
            "loan_type",
            loan_type,
            f"Loan type must be one of: {', '.join(sorted(allowed_types))}"
        ))
    return errors

def validate_application_date(
        date_str: str,
        fmt: str = "%Y-%m-%d") -> Tuple[
    Optional[str], List[ValidationError]]:
    """Validate application date using core date validator."""
    return validate_date("application_date", date_str, fmt,
                        allow_future=False, max_age_years=5)

def validate_branch_code(branch_code: str) -> List[ValidationError]:
    """Validate branch code using core validator."""
    return core_validate_branch_code(branch_code)


def validate_application_record(
        record: Dict[str, Any]) -> Tuple[
    Dict[str, Any], List[ValidationError]]:
    """
    Orchestrate all validators for complete application record.

    Args:
        record: Raw application record dictionary

    Returns:
        Tuple of (validated_record, errors)

    Example:
        >>> record = {'ssn': '123-45-6789', 'loan_amount': 'invalid', ...}
        >>> validated, errors = validate_application_record(record)
        >>>
        >>> if errors:
        ...     # Errors have PII masked automatically
        ...     for error in errors:
        ...         print(error)  # Shows masked values
    """
    all_errors = []
    validated_record = record.copy()

    # Validate SSN
    ssn_errors = validate_ssn(record.get("ssn", ""))
    all_errors.extend(ssn_errors)

    # Validate loan amount
    amount, amount_errors = validate_loan_amount(
        record.get("loan_amount", ""))
    all_errors.extend(amount_errors)
    if amount is not None:
        validated_record["loan_amount"] = amount

    # Validate loan type
    loan_type = record.get("loan_type", "")
    type_errors = validate_loan_type(loan_type)
    all_errors.extend(type_errors)
    if not type_errors:
        validated_record["loan_type"] = loan_type.upper()

    # Validate application date
    date_val, date_errors = validate_application_date(
        record.get("application_date", ""))
    all_errors.extend(date_errors)

    # Validate branch code
    branch_errors = validate_branch_code(
        record.get("branch_code", ""))
    all_errors.extend(branch_errors)

    return (validated_record if not all_errors else record,
            all_errors)


def validate_customer_record(
        record: Dict[str, Any]) -> Tuple[
    Dict[str, Any], List[ValidationError]]:
    """Validate customer record."""
    all_errors = []
    validated_record = record.copy()

    # Validate SSN
    ssn_errors = validate_ssn(record.get("ssn", ""))
    all_errors.extend(ssn_errors)

    # Validate Credit Score
    score_str = record.get("credit_score", "")
    val, score_errors = validate_numeric_range(
        "credit_score", score_str, 300, 850)
    all_errors.extend(score_errors)
    if val is not None:
        validated_record["credit_score"] = int(val)

    # Validate Branch Code
    branch_errors = validate_branch_code(
        record.get("branch_code", ""))
    all_errors.extend(branch_errors)

    return (validated_record if not all_errors else record,
            all_errors)


def validate_branch_record(
        record: Dict[str, Any]) -> Tuple[
    Dict[str, Any], List[ValidationError]]:
    """Validate branch record."""
    all_errors = []
    validated_record = record.copy()

    # Validate employee count
    count_str = record.get("employee_count", "")
    val, count_errors = validate_numeric_range(
        "employee_count", count_str, 0, 1000)
    all_errors.extend(count_errors)
    if val is not None:
        validated_record["employee_count"] = int(val)

    # Validate branch code
    branch_errors = validate_branch_code(
        record.get("branch_code", ""))
    all_errors.extend(branch_errors)

    return (validated_record if not all_errors else record,
            all_errors)


def validate_collateral_record(
        record: Dict[str, Any]) -> Tuple[
    Dict[str, Any], List[ValidationError]]:
    """Validate collateral record."""
    all_errors = []
    validated_record = record.copy()

    # Validate collateral value
    val_str = record.get("collateral_value", "")
    val, val_errors = validate_numeric_range(
        "collateral_value", val_str, 1000, 10_000_000)
    all_errors.extend(val_errors)
    if val is not None:
        validated_record["collateral_value"] = int(val)

    # Validate collateral type
    c_type = record.get("collateral_type", "").upper()
    allowed = {"PROPERTY", "VEHICLE", "SECURITIES", "EQUIPMENT"}
    if c_type not in allowed:
        all_errors.append(
            ValidationError("collateral_type", c_type,
                          f"Must be one of {allowed}"))

    return (validated_record if not all_errors else record,
            all_errors)

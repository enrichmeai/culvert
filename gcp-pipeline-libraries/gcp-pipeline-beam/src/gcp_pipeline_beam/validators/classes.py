"""Composable, class-based validators.

The framework's older, function-style validators (``validate_numeric_range``,
``validate_date``, …) remain supported. These class wrappers provide a
chainable, composable equivalent used by ``SchemaValidator`` and covered in
the book (Chapter 7).

All validators follow the same contract:

- ``validate(value) -> ValidationResult``
- ``ValidationResult.is_valid`` — bool
- ``ValidationResult.errors``   — ``List[ValidationError]``

A ``ValidationResult`` can be unioned with another via the ``|`` operator so
that composition is natural:

    result = RequiredValidator().validate(v) | RegexValidator(r"^\\d+$").validate(v)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Pattern, Sequence

from .types import ValidationError
from .numeric import validate_numeric_range
from .date import validate_date


@dataclass
class ValidationResult:
    """Outcome of applying one or more validators to a single field value."""

    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.is_valid

    def __or__(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=[*self.errors, *other.errors],
        )

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(is_valid=True, errors=[])

    @classmethod
    def invalid(cls, field_name: str, value, message: str,
                error_type: str = "VALIDATION_ERROR") -> "ValidationResult":
        return cls(
            is_valid=False,
            errors=[ValidationError(
                field=field_name,
                value="" if value is None else str(value),
                message=message,
                error_type=error_type,
            )],
        )


class BaseValidator:
    """Abstract base for composable validators.

    Subclasses implement ``validate()``. The base class does nothing by itself;
    its purpose is to document the contract and let callers rely on
    ``isinstance``.
    """

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        raise NotImplementedError  # pragma: no cover


class RequiredValidator(BaseValidator):
    """Fails on ``None``, empty string, or whitespace-only string."""

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult.invalid(
                field_name, value, f"{field_name} is required",
                error_type="REQUIRED",
            )
        return ValidationResult.ok()


class RegexValidator(BaseValidator):
    """Pattern match against a single regular expression."""

    def __init__(self, pattern: str, flags: int = 0, message: Optional[str] = None):
        self.pattern: Pattern = re.compile(pattern, flags)
        self.message = message or f"value does not match pattern {pattern!r}"

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        if value is None:
            return ValidationResult.ok()  # Let RequiredValidator own null policy.
        if not self.pattern.fullmatch(str(value)):
            return ValidationResult.invalid(
                field_name, value, self.message, error_type="PATTERN",
            )
        return ValidationResult.ok()


class DateValidator(BaseValidator):
    """Parses a date string against one or more format candidates."""

    def __init__(self, formats: Sequence[str] = ("%Y-%m-%d", "%Y%m%d")):
        self.formats = tuple(formats)

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult.ok()
        _, errors = validate_date(value, field_name, self.formats)
        if errors:
            return ValidationResult(is_valid=False, errors=list(errors))
        return ValidationResult.ok()


class NumericValidator(BaseValidator):
    """Coerces to float; optionally enforces a range."""

    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ):
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult.ok()
        _, errors = validate_numeric_range(
            value, field_name, min_value=self.min_value, max_value=self.max_value,
        )
        if errors:
            return ValidationResult(is_valid=False, errors=list(errors))
        return ValidationResult.ok()


class SSNValidator(RegexValidator):
    """US Social Security Number (NNN-NN-NNNN or NNNNNNNNN)."""

    def __init__(self):
        super().__init__(
            r"\d{3}-?\d{2}-?\d{4}",
            message="SSN must match NNN-NN-NNNN or NNNNNNNNN",
        )

    def validate(self, value, field_name: str = "ssn") -> ValidationResult:
        return super().validate(value, field_name)


class PostcodeValidator(RegexValidator):
    """UK postcode validator, case-insensitive, optional middle space."""

    def __init__(self):
        super().__init__(
            r"[A-Z]{1,2}[0-9R][0-9A-Z]? ?[0-9][A-Z]{2}",
            flags=re.IGNORECASE,
            message="not a valid UK postcode",
        )


class CompositeValidator(BaseValidator):
    """Runs a sequence of validators and unions their results."""

    def __init__(self, validators: Iterable[BaseValidator]):
        self.validators = list(validators)

    def validate(self, value, field_name: str = "value") -> ValidationResult:
        result = ValidationResult.ok()
        for v in self.validators:
            result = result | v.validate(value, field_name)
        return result


__all__ = [
    "ValidationResult",
    "BaseValidator",
    "RequiredValidator",
    "RegexValidator",
    "DateValidator",
    "NumericValidator",
    "SSNValidator",
    "PostcodeValidator",
    "CompositeValidator",
]

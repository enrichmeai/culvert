"""FieldViolation — a single field-level violation found during validation.

Mirrors ``com.enrichmeai.culvert.dataquality.FieldViolation`` (Java
record, Sprint 14 / issue #73).

Port: T18.2 / issue #118.
"""

from __future__ import annotations

from dataclasses import dataclass

from data_pipeline_core.dataquality.violation_kind import ViolationKind


@dataclass(frozen=True)
class FieldViolation:
    """A single field-level violation produced during data-quality validation.

    Mirrors the Java record ``FieldViolation(String fieldName,
    ViolationKind violationKind, String detail)`` (Java lines 19-28).

    Instances are collected into a
    :class:`~data_pipeline_core.dataquality.ValidationResult.InvalidRow`
    by :class:`~data_pipeline_core.dataquality.DataQualityTransform`.

    All three fields are required and must be non-``None``; ``frozen=True``
    mirrors Java's ``record`` immutability.
    """

    field_name: str
    """Name of the field that failed validation.  Mirrors ``fieldName`` (Java line 21)."""

    violation_kind: ViolationKind
    """Category of violation.  Mirrors ``violationKind`` (Java line 22)."""

    detail: str
    """Human-readable description including expected/actual values.
    Mirrors ``detail`` (Java line 23)."""

    def __post_init__(self) -> None:
        # Mirrors Java Objects.requireNonNull guards (Java lines 24-27).
        if self.field_name is None:
            raise ValueError("field_name must not be None")
        if self.violation_kind is None:
            raise ValueError("violation_kind must not be None")
        if self.detail is None:
            raise ValueError("detail must not be None")

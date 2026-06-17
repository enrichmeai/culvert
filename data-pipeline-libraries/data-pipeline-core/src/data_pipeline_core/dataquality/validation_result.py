"""ValidationResult — either-style result of validating a single row.

Mirrors ``com.enrichmeai.culvert.dataquality.ValidationResult`` (Java
sealed interface + two record subtypes, Sprint 14 / issue #73).

Python has no sealed interfaces; we use a frozen-dataclass hierarchy
with an abstract-base-class sentinel and two concrete subtypes.

Port: T18.2 / issue #118.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Sequence, Tuple, TypeVar

from data_pipeline_core.dataquality.field_violation import FieldViolation

R = TypeVar("R")


@dataclass(frozen=True)
class ValidationResult(Generic[R]):
    """Abstract base for validation results.

    Mirrors the Java sealed interface ``ValidationResult<R>`` (Java
    lines 30-76).  Two concrete subtypes:

    * :class:`ValidRow` — every field passed all checks (Java lines 50-54).
    * :class:`InvalidRow` — one or more fields failed; carries a non-empty
      tuple of :class:`~data_pipeline_core.dataquality.FieldViolation` instances
      (Java lines 63-75).

    The base class provides :meth:`is_valid` (mirrors Java default method
    at line 37-39) and exposes the common ``row`` accessor for symmetric
    access from both subtypes.
    """

    row: R
    """The original row — present in both subtypes. Mirrors ``row()`` (Java line 35)."""

    def is_valid(self) -> bool:
        """Return ``True`` iff this result is a :class:`ValidRow`.

        Mirrors ``ValidationResult.isValid()`` (Java lines 37-39).
        """
        return isinstance(self, ValidRow)


@dataclass(frozen=True)
class ValidRow(ValidationResult[R], Generic[R]):
    """A row that passed all data-quality checks.

    Mirrors ``ValidationResult.ValidRow<R>`` (Java lines 50-54).
    ``row`` must not be ``None`` (mirrors Java's ``Objects.requireNonNull``
    at Java line 52).
    """

    def __post_init__(self) -> None:
        if self.row is None:
            raise ValueError("row must not be None")


@dataclass(frozen=True)
class InvalidRow(ValidationResult[R], Generic[R]):
    """A row that failed one or more data-quality checks.

    Mirrors ``ValidationResult.InvalidRow<R>`` (Java lines 63-75).

    ``violations`` is stored as an immutable ``tuple`` (mirrors
    ``List.copyOf`` at Java line 73) and is guaranteed non-empty
    (mirrors Java's guard at lines 69-72).
    """

    violations: Tuple[FieldViolation, ...]
    """Non-empty tuple of field violations, one per failing field."""

    def __post_init__(self) -> None:
        # Mirrors Java guards (lines 67-73).
        if self.row is None:
            raise ValueError("row must not be None")
        if self.violations is None:
            raise ValueError("violations must not be None")
        if len(self.violations) == 0:
            raise ValueError("InvalidRow must have at least one FieldViolation")

    @classmethod
    def of(cls, row: R, violations: Sequence[FieldViolation]) -> "InvalidRow[R]":
        """Convenience factory that accepts any sequence and converts to tuple."""
        return cls(row=row, violations=tuple(violations))

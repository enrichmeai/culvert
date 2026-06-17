"""NumericRange — closed inclusive numeric range [min, max].

Mirrors ``com.enrichmeai.culvert.dataquality.NumericRange`` (Java
record, Sprint 14 / issue #73; schema-grounded T14.7 / issue #100).

Port: T18.2 / issue #118.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericRange:
    """A closed numeric range ``[min, max]`` (both bounds inclusive).

    Used by :class:`~data_pipeline_core.dataquality.DataQualityTransform`
    to detect ``OUT_OF_RANGE`` field values.  Mirrors the Java record
    ``NumericRange(double min, double max)`` (Java lines 20–42):

    * Both bounds are ``float`` (Python) / ``double`` (Java).
    * ``max`` must be ``>=`` ``min`` — ``ValueError`` otherwise (mirrors
      ``IllegalArgumentException`` at Java line 24).
    * :meth:`contains` mirrors ``NumericRange.contains(double)`` (Java
      line 39).

    Attach a ``NumericRange`` to a :class:`~data_pipeline_core.schema.entity.SchemaField`
    via ``SchemaField(... range=NumericRange.of(lo, hi))`` to opt that
    field into range validation.
    """

    min: float
    max: float

    def __post_init__(self) -> None:
        # Mirrors Java compact constructor (NumericRange.java:22-27).
        if self.max < self.min:
            raise ValueError(
                f"max ({self.max}) must be >= min ({self.min})"
            )

    @classmethod
    def of(cls, min: float, max: float) -> "NumericRange":
        """Convenience factory — mirrors ``NumericRange.of(double, double)``
        (Java line 30)."""
        return cls(min=min, max=max)

    def contains(self, value: float) -> bool:
        """Return ``True`` iff ``value`` lies within ``[min, max]`` inclusive.

        Mirrors ``NumericRange.contains(double)`` (Java lines 39-41).
        """
        return self.min <= value <= self.max

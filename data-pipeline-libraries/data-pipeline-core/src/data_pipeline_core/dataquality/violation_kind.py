"""ViolationKind — classification of a single field violation.

Mirrors ``com.enrichmeai.culvert.dataquality.ViolationKind`` (Java
Sprint 14 / issue #73).  Three variants, same names, same semantics.

Port: T18.2 / issue #118.
"""

from __future__ import annotations

from enum import Enum


class ViolationKind(Enum):
    """Classification of a single field violation found during validation.

    Mirrors ``ViolationKind.java`` (see
    ``data-pipeline-libraries-java/.../dataquality/ViolationKind.java``):

    * ``MISSING_REQUIRED`` — a field declared ``REQUIRED`` had a ``None``
      or absent value. (Java line 25)
    * ``TYPE_MISMATCH``    — the field's runtime type does not match the
      schema-declared wire type. (Java line 28)
    * ``OUT_OF_RANGE``     — a numeric field falls outside its declared
      :class:`NumericRange`. (Java line 31)
    """

    MISSING_REQUIRED = "MISSING_REQUIRED"
    """The field is declared REQUIRED but its value is None or missing."""

    TYPE_MISMATCH = "TYPE_MISMATCH"
    """The field's runtime value type does not match the schema wire type."""

    OUT_OF_RANGE = "OUT_OF_RANGE"
    """The field's numeric value falls outside its declared NumericRange."""

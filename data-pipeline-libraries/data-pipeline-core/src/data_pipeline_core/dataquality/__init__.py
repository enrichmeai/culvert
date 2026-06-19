"""dataquality — cloud-neutral data-quality validation for Culvert pipelines.

Port of ``com.enrichmeai.culvert.dataquality.*`` (Java Sprint 14 / issue #73;
T14.4 / issue #76; T14.7 / issue #100) to Python.  T18.2 / issue #118.

Five types, same shapes, same semantics:

* :class:`ViolationKind`         — enum: MISSING_REQUIRED | TYPE_MISMATCH | OUT_OF_RANGE
* :class:`NumericRange`          — closed inclusive [min, max] with ``contains()``
* :class:`FieldViolation`        — (field_name, violation_kind, detail) triple
* :class:`ValidationResult`      — base; subclasses: :class:`ValidRow`, :class:`InvalidRow`
* :class:`DataQualityTransform`  — implements Transform[R, ValidationResult[R]]

Typical usage::

    from data_pipeline_core.dataquality import (
        DataQualityTransform,
        InvalidRow,
        NumericRange,
        ValidRow,
        ValidationResult,
        ViolationKind,
    )
"""

from data_pipeline_core.dataquality.data_quality_transform import DataQualityTransform
from data_pipeline_core.dataquality.field_violation import FieldViolation
from data_pipeline_core.dataquality.numeric_range import NumericRange
from data_pipeline_core.dataquality.validation_result import (
    InvalidRow,
    ValidRow,
    ValidationResult,
)
from data_pipeline_core.dataquality.violation_kind import ViolationKind

__all__ = [
    "DataQualityTransform",
    "FieldViolation",
    "InvalidRow",
    "NumericRange",
    "ValidRow",
    "ValidationResult",
    "ViolationKind",
]

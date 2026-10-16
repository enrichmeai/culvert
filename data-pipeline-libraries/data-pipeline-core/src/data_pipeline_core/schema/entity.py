"""SchemaField and EntitySchema — cloud-neutral typed schema model.

The model is deliberately cloud-neutral: no `to_bq_schema()`-style
convenience methods here — cloud-specific schema conversions belong
in the adapter packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy

if TYPE_CHECKING:
    # Guarded to avoid a circular import at runtime:
    # dataquality.NumericRange is in a peer sub-package that itself imports
    # SchemaField.  At type-check time (mypy/pyright) the import is fine;
    # at runtime the annotation is a string-forward-ref thanks to
    # `from __future__ import annotations`.
    from data_pipeline_core.dataquality.numeric_range import NumericRange


@dataclass(frozen=True)
class SchemaField:
    """A single field in an EntitySchema.

    `mode` is one of `REQUIRED`, `NULLABLE`, `REPEATED` — matches
    BigQuery's vocabulary because it's the framework's first reference
    warehouse, but the values are warehouse-neutral.

    `masking` is the policy `@masked(schema=...)` applies to this field
    when no explicit policy names it. `classification` is descriptive
    metadata: `@governed` reports the GovernancePolicy's `classify`
    answer, not this field.

    `range` is an optional :class:`~data_pipeline_core.dataquality.NumericRange`
    that opts this field into OUT_OF_RANGE validation inside
    :class:`~data_pipeline_core.dataquality.DataQualityTransform`.
    Mirrors ``SchemaField.range()`` (Java T14.7 / issue #100).

    `allowed` is an optional list of the values a STRING field may hold
    (#259). It opts the field into NOT_ALLOWED validation: a value must
    equal one of them exactly. A sequence is stored as a tuple; it must be
    non-empty, hold only non-blank strings and repeat none. Mirrors
    ``SchemaField.allowed()`` in Java.
    """

    name: str
    type: str  # e.g. "STRING", "INT64", "FLOAT64", "TIMESTAMP", "DATE", "BOOL"
    mode: str = "NULLABLE"  # REQUIRED | NULLABLE | REPEATED
    description: Optional[str] = None
    classification: Optional[DataClassification] = None
    masking: Optional[MaskingPolicy] = None
    # Sprint-18 / T18.2: added additively to support schema-grounded range
    # validation in DataQualityTransform.  Existing callers that omit this
    # field are unaffected (default None → range validation skipped).
    range: Optional["NumericRange"] = None
    allowed: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        if self.allowed is None:
            return
        if self.type != "STRING":
            raise ValueError(
                f"allowed values are for STRING fields, and '{self.name}' is {self.type}"
            )
        if isinstance(self.allowed, str) or not isinstance(self.allowed, Sequence):
            raise ValueError("allowed must be a sequence of strings, not a single value")
        values = tuple(self.allowed)
        if not values:
            raise ValueError("allowed must not be empty")
        seen = set()
        for value in values:
            if not isinstance(value, str):
                raise ValueError("allowed values must be strings")
            if all(c.isspace() and c != "\x85" for c in value):
                raise ValueError("allowed values must not be blank")
            if value in seen:
                raise ValueError(f"duplicate allowed value '{value}'")
            seen.add(value)
        object.__setattr__(self, "allowed", values)


@dataclass(frozen=True)
class EntitySchema:
    """A named schema for an entity (a logical table or file structure).

    `version` enables schema evolution: two `EntitySchema` instances
    with the same name and different versions can coexist, and the
    framework picks the right one based on the record being processed.
    """

    name: str
    fields: List[SchemaField]
    version: str = "1"
    description: Optional[str] = None
    primary_key: List[str] = field(default_factory=list)
    partition_key: Optional[str] = None  # for partitioned tables; opaque

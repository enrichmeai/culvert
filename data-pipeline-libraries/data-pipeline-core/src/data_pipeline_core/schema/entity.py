"""SchemaField and EntitySchema — cloud-neutral typed schema model.

The model is deliberately cloud-neutral: no `to_bq_schema()`-style
convenience methods here — cloud-specific schema conversions belong
in the adapter packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

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

    `classification` and `masking` are optional metadata used by the
    `@governed` and `@masked` decorators (Stage 3) to apply
    field-level policy without requiring an explicit decorator call.

    `range` is an optional :class:`~data_pipeline_core.dataquality.NumericRange`
    that opts this field into OUT_OF_RANGE validation inside
    :class:`~data_pipeline_core.dataquality.DataQualityTransform`.
    Mirrors ``SchemaField.range()`` (Java T14.7 / issue #100).
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

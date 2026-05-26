"""SchemaField and EntitySchema — cloud-neutral typed schema model.

Mirrors the existing `gcp_pipeline_core.schema.SchemaField` /
`EntitySchema` shape, minus the `to_bq_schema()` convenience method.
That method moves to `data-pipeline-gcp-bigquery` as an extension
function (Stage 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy


@dataclass(frozen=True)
class SchemaField:
    """A single field in an EntitySchema.

    `mode` is one of `REQUIRED`, `NULLABLE`, `REPEATED` — matches
    BigQuery's vocabulary because it's the framework's first reference
    warehouse, but the values are warehouse-neutral.

    `classification` and `masking` are optional metadata used by the
    `@governed` and `@masked` decorators (Stage 3) to apply
    field-level policy without requiring an explicit decorator call.
    """

    name: str
    type: str  # e.g. "STRING", "INT64", "FLOAT64", "TIMESTAMP", "DATE", "BOOL"
    mode: str = "NULLABLE"  # REQUIRED | NULLABLE | REPEATED
    description: Optional[str] = None
    classification: Optional[DataClassification] = None
    masking: Optional[MaskingPolicy] = None


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

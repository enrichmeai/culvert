"""GovernancePolicy — resolves what masking, retention, and
classification apply to a given field or table.

Implementations may consult Dataplex (GCP), Glue Data Catalog (AWS),
Purview (Azure), or a static YAML file shipped with the project. The
framework's default is `StaticGovernancePolicy` (added in Stage 3),
which reads a YAML file and runs without any cloud service.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import (
    MaskingPolicy,
    RetentionPolicy,
)


@runtime_checkable
class GovernancePolicy(Protocol):
    """Field- and table-level policy lookups.

    The three methods are called by Stage 3's `@governed` and
    `@masked` decorators to apply policy without requiring the
    pipeline author to know which cloud governance product is in use.
    """

    def classify(self, field: str, table: str) -> DataClassification:
        """Return the sensitivity classification of `field` in `table`.

        Defaults to `DataClassification.INTERNAL` when no policy
        attaches — never raises.
        """
        ...

    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
        """Return the masking policy for `field` in `table`, or None if
        no masking applies."""
        ...

    def retention_for(self, table: str) -> Optional[RetentionPolicy]:
        """Return the retention policy for `table`, or None if no
        retention policy applies (data kept indefinitely)."""
        ...

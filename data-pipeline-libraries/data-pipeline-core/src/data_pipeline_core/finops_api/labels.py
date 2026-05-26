"""FinOpsTag — cost-attribution metadata.

Replaces the existing `FinOpsLabels` class. The name change is
intentional: "labels" is a GCP-specific term (BigQuery/GCS labels);
"tags" is the universal vocabulary (AWS tags, Azure tags, GCP labels
all map to it cleanly). The Stage 1 deprecation shim will export
`FinOpsLabels` as an alias for `FinOpsTag` with a `DeprecationWarning`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class FinOpsTag:
    """Cost-attribution metadata attached to every emitted cost metric.

    The five required fields are the minimum useful tag set. `extra`
    carries arbitrary additional tags the team wants to attribute by
    (e.g. `business_unit`, `customer_id`, `feature_flag`).
    """

    system: str
    environment: str
    cost_center: str
    owner: str
    run_id: str
    extra: Mapping[str, str] = field(default_factory=dict)

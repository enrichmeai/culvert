"""FinOpsSink — receives CostMetrics from cloud-specific cost trackers.

Cloud-specific cost trackers (`BigQueryCostTracker`,
`CloudStorageCostTracker`, `PubSubCostTracker`) produce `CostMetrics`;
this Protocol is the aggregation seam that records them.
`BigQueryFinOpsSink` (in `data-pipeline-gcp-bigquery`) writes the
metrics to a BigQuery cost-metrics table.

`FinOpsTag` is passed explicitly rather than read from the runtime
context. Cost emissions are infrequent and lossy attribution is the
most common bug; explicit tags make the data flow visible.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics


@runtime_checkable
class FinOpsSink(Protocol):
    """Aggregates cost metrics with attribution tags.

    Implementations may batch internally. The framework calls
    `record()` once per cost-incurring operation (a BigQuery query, a
    GCS upload, a Pub/Sub publish); the sink is responsible for
    flushing on its own schedule.
    """

    def record(self, metrics: CostMetrics, tags: FinOpsTag) -> None: ...

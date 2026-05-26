"""FinOpsSink — receives CostMetrics from cloud-specific cost trackers.

Today's `gcp_pipeline_core.finops.tracker` has cloud-specific cost
trackers (`BigQueryCostTracker`, `CloudStorageCostTracker`,
`PubSubCostTracker`) that produce `CostMetrics`, but no aggregation
layer that records them. This Protocol fills that gap. Stage 2's
`BigQueryFinOpsSink` will write the metrics to a BigQuery cost-metrics
table.

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

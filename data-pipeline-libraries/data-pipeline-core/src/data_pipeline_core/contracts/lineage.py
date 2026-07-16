"""LineageEmitter — publishes OpenLineage-shaped events.

Implementations emit a `LineageEvent` — a dict of four sub-dicts
(`source`/`pipeline`/`destination`/`audit`) — at stage boundaries.
The GCP implementation is `DataCatalogLineageEmitter` in
`data-pipeline-gcp-observability`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from data_pipeline_core.lineage.events import LineageEvent


@runtime_checkable
class LineageEmitter(Protocol):
    """Publishes lineage events at pipeline-stage boundaries.

    Implementations should batch by `run_id` and emit on stage
    completion. The default cloud-neutral implementation
    (`OpenLineageEmitter`, added in Stage 3) targets a Marquez or
    OpenLineage Proxy endpoint. GCP implementation:
    `data_pipeline_gcp_dataplex.DataplexLineagePublisher`.
    """

    def emit(self, event: LineageEvent) -> None: ...

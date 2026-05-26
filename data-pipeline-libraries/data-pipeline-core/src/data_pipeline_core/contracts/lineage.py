"""LineageEmitter — publishes OpenLineage-shaped events.

Existing GCP-adjacent shape:
`gcp_pipeline_core.audit.lineage.DataLineageTracker.generate_data_lineage`
returns a dict with the four sub-dicts captured by `LineageEvent`.
Stage 2 will adapt that static method into an instance method that
satisfies this Protocol.
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

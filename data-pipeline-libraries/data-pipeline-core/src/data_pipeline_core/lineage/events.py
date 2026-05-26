"""LineageEvent — a TypedDict that pins down the OpenLineage-shaped
event the framework emits at stage boundaries.

The shape mirrors what
`gcp_pipeline_core.audit.lineage.DataLineageTracker.generate_data_lineage`
returns today (a dict with `source`/`pipeline`/`destination`/`audit`
sub-dicts). Capturing it as a TypedDict here makes the LineageEmitter
Protocol's argument type inspectable for Stage 2 implementers.

These are intentionally `total=False` because not every stage produces
every section (e.g. a streaming source emits no `destination` until the
first window closes).
"""

from __future__ import annotations

from typing import Any, Mapping, TypedDict


class LineageSource(TypedDict, total=False):
    """The upstream artefact lineage is being traced from."""

    type: str  # e.g. "file", "table", "topic"
    uri: str  # opaque URI: gs://..., s3://..., bigquery://...
    schema: Mapping[str, Any]
    metadata: Mapping[str, Any]


class LineagePipeline(TypedDict, total=False):
    """The pipeline run that produced this lineage edge."""

    run_id: str
    pipeline_name: str
    stage: str
    started_at: str  # ISO8601
    completed_at: str  # ISO8601


class LineageDestination(TypedDict, total=False):
    """The downstream artefact records were written to."""

    type: str
    uri: str
    schema: Mapping[str, Any]
    metadata: Mapping[str, Any]


class LineageAudit(TypedDict, total=False):
    """Reconciliation summary attached to the edge."""

    record_count_source: int
    record_count_destination: int
    error_count: int
    audit_hash: str


class LineageEvent(TypedDict, total=False):
    """OpenLineage-shaped event emitted at a pipeline-stage boundary.

    Keys mirror the dict that today's `DataLineageTracker.generate_data_lineage`
    produces. Stage 2 will refactor that method to return this TypedDict.
    """

    source: LineageSource
    pipeline: LineagePipeline
    destination: LineageDestination
    audit: LineageAudit

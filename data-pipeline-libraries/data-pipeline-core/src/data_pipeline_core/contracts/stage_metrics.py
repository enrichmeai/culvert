"""StageMetrics + StageMetricsHook — typed per-stage pipeline metrics.

Mirrors the Java Sprint-12 / issue #65 additions:

* ``StageMetrics`` — immutable snapshot of the three Culvert standard
  metrics plus the three label dimensions. Python equivalent of the
  Java ``record StageMetrics``.

* ``StageMetricsHook`` — cloud-neutral contract for emitting per-stage
  pipeline metrics. Python equivalent of the Java
  ``interface StageMetricsHook``.

Why a new protocol instead of ``ObservabilityHook``?
``ObservabilityHook`` is a general-purpose surface (arbitrary name +
tags). This contract codifies the Culvert-specific semantic: one call
per stage completion emits exactly the three Culvert metric series
(``culvert/rows_processed``, ``culvert/stage_latency_ms``,
``culvert/error_count``) with a fixed label schema. That specificity
enables type-safe constructors, clear mock-based testing, and prevents
callers from accidentally mis-naming labels.

Sprint-12 / issue #65; Python gap closed in T17.1 / issue #113.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StageMetrics:
    """Immutable snapshot of metrics for a single pipeline stage completion.

    Carries the three Culvert standard metrics plus the three label
    dimensions required by :class:`StageMetricsHook` implementations:

    Labels:
        pipeline_id:  metric label ``pipeline_id``
        run_id:       metric label ``run_id``
        stage_name:   metric label ``stage_name``

    Metrics:
        rows_processed:   ``culvert/rows_processed`` (CUMULATIVE INT64).
                          Use ``0`` as the "unknown" sentinel for stages
                          that do not surface element counts.
        stage_latency_ms: ``culvert/stage_latency_ms`` (GAUGE DOUBLE).
        error_count:      ``culvert/error_count`` (CUMULATIVE INT64).

    This is a plain Python dataclass — frozen (immutable) to mirror the
    Java record semantics. No cloud or framework imports.
    """

    pipeline_id: str
    run_id: str
    stage_name: str
    rows_processed: int
    stage_latency_ms: float
    error_count: int

    def __post_init__(self) -> None:
        """Validate that the three label fields are non-None."""
        if self.pipeline_id is None:
            raise ValueError("pipeline_id must not be None")
        if self.run_id is None:
            raise ValueError("run_id must not be None")
        if self.stage_name is None:
            raise ValueError("stage_name must not be None")


@runtime_checkable
class StageMetricsHook(Protocol):
    """Cloud-neutral contract for emitting per-stage pipeline metrics.

    This Protocol is deliberately narrow: one method, one value type,
    three fixed metrics (``rows_processed``, ``stage_latency_ms``,
    ``error_count``) labelled by
    ``pipeline_id``/``run_id``/``stage_name``. The narrowness is
    intentional — it makes the GCP implementation testable in isolation
    and keeps Beam/Dataflow wiring (which assembles the call-site) in a
    separate module.

    Implementations must not propagate monitoring-backend failures to the
    caller. If the backend is unavailable the implementation logs and
    swallows the exception so the pipeline continues uninterrupted.

    See also: :class:`StageMetrics`, :class:`~data_pipeline_core.contracts.observability.ObservabilityHook`
    """

    def record_stage_metrics(self, metrics: StageMetrics) -> None:
        """Record metrics for a completed pipeline stage.

        Implementations must not propagate monitoring-backend failures to
        the caller. If the backend is unavailable the implementation logs
        and swallows the exception so the pipeline continues uninterrupted.

        Args:
            metrics: Stage metrics snapshot. Must not be None.
        """
        ...

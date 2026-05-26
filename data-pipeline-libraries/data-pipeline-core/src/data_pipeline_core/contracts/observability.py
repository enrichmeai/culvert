"""ObservabilityHook — the single observability seam.

Metrics, logs, and traces all flow through this. Today's code splits
the surface across `MetricsCollector` (counter/gauge/histogram),
`StructuredLogger` (log), and OTEL helpers (span). Stage 2 introduces
a `CompositeObservabilityHook` that delegates to all three internally;
the Protocol stays monolithic so user code has one dependency to
inject, not three.

This is a deliberate divergence from the existing split: the redesign
(section 8) commits to one observability seam. Implementations are
free to compose multiple backends internally.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Mapping, Protocol, runtime_checkable


# A reasonable default for the optional `tags` mappings on metric calls.
_NO_TAGS: Mapping[str, str] = {}


@runtime_checkable
class ObservabilityHook(Protocol):
    """Single seam for metrics, structured logs, and traces.

    `tags` follow OpenTelemetry attribute conventions (string keys,
    string values). Cardinality is the implementation's concern;
    high-cardinality tag values (e.g. `run_id`) should be added to
    spans/logs but kept off metric labels.
    """

    def counter(
        self,
        name: str,
        value: int = 1,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Increment a monotonic counter named `name` by `value`."""
        ...

    def gauge(
        self,
        name: str,
        value: float,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Set the current value of gauge `name` to `value`."""
        ...

    def histogram(
        self,
        name: str,
        value: float,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Record an observation of `value` into histogram `name`."""
        ...

    def log(self, level: str, message: str, **fields: Any) -> None:
        """Emit a structured log line.

        `level` is one of `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`
        (case-insensitive). `**fields` become structured attributes
        on the log record.
        """
        ...

    def span(self, name: str) -> AbstractContextManager[Any]:
        """Open a tracing span named `name`. Use as a context manager.

        The yielded object is implementation-defined; most callers
        ignore it. Exceptions raised inside the `with` block are
        recorded on the span.
        """
        ...

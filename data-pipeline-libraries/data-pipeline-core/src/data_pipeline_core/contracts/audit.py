"""AuditEventPublisher — emits audit records.

Implementations publish `AuditRecord`s to an event bus (Pub/Sub on
GCP). `publish()` may buffer; `flush()` blocks until everything
buffered has been acknowledged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from data_pipeline_core.audit.records import AuditRecord


@runtime_checkable
class AuditEventPublisher(Protocol):
    """Publishes audit records.

    Implementations may batch internally for throughput, but must
    guarantee at-least-once delivery within a single `run_id`
    boundary. `flush()` blocks until all buffered records have been
    acknowledged by the backing event bus.
    """

    def publish(self, record: AuditRecord) -> None:
        """Publish a single audit record. May buffer."""
        ...

    def flush(self) -> None:
        """Block until all buffered records have been acknowledged.

        Called at pipeline-stage boundaries and at shutdown.
        Idempotent — calling `flush()` on an empty buffer is a no-op.
        """
        ...

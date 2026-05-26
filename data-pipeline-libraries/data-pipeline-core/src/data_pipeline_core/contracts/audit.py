"""AuditEventPublisher — emits audit records.

Existing GCP implementation: `gcp_pipeline_core.audit.publisher`'s
`AuditPublisher` (Pub/Sub-backed). It returns a Pub/Sub message ID
from `publish()` today; Stage 2 will adapt that to return None to
satisfy this Protocol. It does not have a `flush()` method today
either (publishers are stateless); the adapter adds a no-op.
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

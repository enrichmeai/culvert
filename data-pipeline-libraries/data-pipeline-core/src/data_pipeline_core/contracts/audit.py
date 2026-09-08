"""AuditEventPublisher - publishes audit events (docs/CONTRACT.md section 4).

Implementations publish `AuditEvent`s to an event bus (Pub/Sub on GCP) or
straight to `job_control.audit_events`. `publish()` may buffer; `flush()`
blocks until everything buffered has been acknowledged.

Python mirror of the Java `com.enrichmeai.culvert.contracts.AuditEventPublisher`
interface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from data_pipeline_core.audit.events import AuditEvent


@runtime_checkable
class AuditEventPublisher(Protocol):
    """Publishes audit events.

    Implementations may batch internally for throughput, but must guarantee
    at-least-once delivery within a single ``run_id`` boundary. :meth:`flush`
    blocks until all buffered events have been acknowledged by the backing
    event bus.

    A failed publish is never silent
    --------------------------------
    How it fails depends on what was being published, and the event itself
    says which - :meth:`AuditEvent.failure_is_fatal`:

    * **Run-level** (``RUN_START``, ``RUN_END``, ``ERROR_RAISED``,
      ``RECONCILIATION``, ``RETRY_ATTEMPTED``) - the publish **raises**. These
      events *are* the run's state; continuing without one is how a pipeline
      reports success it never had.
    * **Aggregate** (``RECORD_VALIDATED``, ``RECORD_REJECTED``) - log at ERROR
      and continue, so an audit hiccup over a counter cannot halt ingestion.

    Implementations **must not** catch-and-continue on a run-level event. The
    previous implementation logged every failure at WARN and swallowed it, so
    an audit trail that had never once written looked healthy for months.

    An implementation that buffers must not defer a run-level failure to
    :meth:`flush` either: a run that dies before its flush would lose the
    failure entirely, which is the same defect wearing a different hat.
    """

    def publish(self, event: AuditEvent) -> None:
        """Publish a single audit event. May buffer.

        Raises:
            Exception: if the event is run-level and the write failed.
                Aggregate events log at ERROR and return instead.
        """
        ...

    def flush(self) -> None:
        """Block until all buffered events have been acknowledged.

        Called at pipeline-stage boundaries and at shutdown.
        Idempotent - calling `flush()` on an empty buffer is a no-op.
        """
        ...

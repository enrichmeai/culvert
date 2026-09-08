"""Deployment-local audit publisher.

Implements Culvert's `AuditEventPublisher` Protocol
(`data_pipeline_core.contracts.audit`) over Pub/Sub: each `AuditEvent`
(docs/CONTRACT.md section 4) is serialised to JSON and published to the
pipeline-events topic.

Why the serialisation is written out by hand
--------------------------------------------
This used to be ``dataclasses.asdict(record)``. Three things were wrong with
that, and only the third was visible:

1. ``EventKind`` and the ``MappingProxyType`` payload are not JSON
   serialisable, so ``asdict`` cannot round-trip an ``AuditEvent`` at all.
2. The wire shape silently followed whatever fields the dataclass happened to
   have - adding or renaming one reshaped every consumer's message with no
   diff at this file.
3. It emitted the pre-0.2.0 stage-summary columns, not section 4's ten.

So the ten contract columns are bound explicitly below, ``None``s included, and
the shape changes only when someone edits this function.

Failure semantics (spine AD-5)
------------------------------
A failed publish is never silent, and the event decides how it surfaces:

* **Run-level** (``RUN_START``, ``RUN_END``, ``ERROR_RAISED``,
  ``RECONCILIATION``, ``RETRY_ATTEMPTED``) - raises. These events *are* the
  run's state.
* **Aggregate** (``RECORD_VALIDATED``, ``RECORD_REJECTED``) - logged at ERROR,
  counted, and ingestion continues.

Pub/Sub publishes asynchronously, so a run-level event is **awaited inline**
rather than buffered: deferring its failure to :meth:`flush` would lose it
entirely for a run that dies before flushing - the same swallow in a new place.
The consequence is an invariant this module holds: ``_pending`` only ever
contains aggregate events, so :meth:`flush` logs and never raises.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

from google.cloud import pubsub_v1

from data_pipeline_core.audit.events import AuditEvent

logger = logging.getLogger(__name__)

# How long to wait for Pub/Sub to acknowledge one message, in seconds.
_ACK_TIMEOUT_SECONDS = 30


class PubSubAuditPublisher:
    """Publishes AuditEvents as JSON messages on a Pub/Sub topic."""

    def __init__(self, project_id: str, topic_name: str,
                 publisher: pubsub_v1.PublisherClient | None = None) -> None:
        self._publisher = publisher or pubsub_v1.PublisherClient()
        self._topic = self._publisher.topic_path(project_id, topic_name)
        # Aggregate events only - see the module docstring.
        self._pending: List[Tuple[AuditEvent, Any]] = []
        self._audit_failures = 0

    @property
    def audit_failure_count(self) -> int:
        """Cumulative audit publish failures since construction.

        The observable that proves an aggregate failure was not swallowed;
        mirrors ``BigQueryAuditEventPublisher.auditFailureCount()`` in Java.
        """
        return self._audit_failures

    def publish(self, event: AuditEvent) -> None:
        """Publish one audit event.

        Run-level events are awaited here and raise on failure. Aggregate
        events are buffered and their failures surface in :meth:`flush`.

        Raises:
            RuntimeError: the event is run-level and the publish failed.
        """
        if event is None:
            raise ValueError("event must not be None")

        try:
            # Serialisation is inside the guard on purpose. AuditEvent
            # validates payload *keys*, never value types, so a Decimal count
            # or a datetime in a payload raises TypeError here - and an
            # aggregate event must not be able to halt ingestion by failing to
            # serialise any more than by failing to send.
            message = json.dumps(_to_wire(event)).encode("utf-8")
            future = self._publisher.publish(
                self._topic,
                message,
                run_id=event.run_id,
                entity=event.entity,
                event_kind=event.event_kind.wire_value,
            )
            if event.failure_is_fatal():
                # Await it: a run-level failure must surface at the call site
                # that decided to emit it, not at some later flush that a
                # dying run may never reach.
                future.result(timeout=_ACK_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - re-raised or logged below
            self._fail(event, exc)
        else:
            if not event.failure_is_fatal():
                self._pending.append((event, future))

    def flush(self) -> None:
        """Block until all buffered events have been acknowledged.

        Only aggregate events are ever buffered, so this logs failures at ERROR
        and never raises. Idempotent: a no-op on an empty buffer.
        """
        pending, self._pending = self._pending, []
        for event, future in pending:
            try:
                future.result(timeout=_ACK_TIMEOUT_SECONDS)
            except Exception as exc:  # noqa: BLE001 - reported by _fail
                self._fail(event, exc)

    def _fail(self, event: AuditEvent, exc: Exception) -> None:
        """Apply AD-5: run-level raises, aggregate logs at ERROR. Never silent."""
        self._audit_failures += 1
        if event.failure_is_fatal():
            raise RuntimeError(
                f"Audit publish FAILED for run-level event "
                f"{event.event_kind.wire_value} run_id={event.run_id} -> "
                f"{self._topic}. Failing the pipeline rather than reporting a "
                f"success that was never recorded."
            ) from exc
        logger.error(
            "Audit publish failed for aggregate event %s run_id=%s entity=%s "
            "payload=%s; ingestion continues, event recoverable from this log",
            event.event_kind.wire_value, event.run_id, event.entity,
            dict(event.payload), exc_info=exc,
        )


def _to_wire(event: AuditEvent) -> Dict[str, Any]:
    """Serialise an AuditEvent to docs/CONTRACT.md section 4's ten columns.

    ``contract_version`` is taken from the event rather than re-read from the
    module constant, so a row originating with a foreign producer round-trips
    with the version it was actually written against.
    """
    return {
        "run_id": event.run_id,
        "system_id": event.system_id,
        "entity": event.entity,
        "event_kind": event.event_kind.wire_value,
        "event_ts": event.event_ts.isoformat(),
        "extract_date": (
            event.extract_date.isoformat() if event.extract_date else None
        ),
        "payload": dict(event.payload),
        "producer": event.producer,
        "contract_version": event.contract_version,
        "environment": event.environment,
    }

"""AuditEventPublisher contract test mixin.

Java mirror: ``com.enrichmeai.culvert.contracttests.AuditEventPublisherContractTest``
(#209), test for test.

From the ``AuditEventPublisher`` Protocol and ``docs/CONTRACT.md`` section 4:

* ``publish`` takes every event kind;
* ``flush`` blocks until buffered events are acknowledged, and is a no-op on an
  empty buffer;
* a failed publish is never silent. A run-level event's failure raises, and an
  aggregate event's failure is logged and the run goes on.

Which kinds are run-level comes from :class:`EventKind` and
:meth:`AuditEvent.failure_is_fatal`, which both languages hold to the shared
fixtures in ``tests/contract/fixtures/audit_events.json``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_pipeline_core.audit.events import AuditEvent, EventKind


def contract_event(kind: EventKind) -> AuditEvent:
    """A valid event of ``kind``: every payload key section 4 requires is present."""
    return AuditEvent(
        run_id="20260908T091400Z-7f3a",
        system_id="Generic",
        entity="customers",
        event_kind=kind,
        event_ts=datetime(2026, 9, 8, 9, 14, tzinfo=timezone.utc),
        payload={key: "contract" for key in kind.required_payload_keys},
    )


_RUN_LEVEL = [k for k in EventKind if k.is_run_level()]
_AGGREGATE = [k for k in EventKind if not k.is_run_level()]


def _wire(kind: EventKind) -> str:
    return kind.wire_value


class AuditEventPublisherContract:
    """Mixin. Subclasses provide three pytest fixtures:

    - ``publisher``: the publisher, over a backend double that accepts writes;
    - ``failing_publisher``: the same implementation, over a backend double
      that fails every write;
    - ``delivered``: a zero-argument callable returning how many events the
      accepting backend has acknowledged.

    Example wiring:

    .. code-block:: python

        class TestMyPublisher(AuditEventPublisherContract):
            @pytest.fixture
            def publisher(self, backend):
                return MyPublisher(backend)

            @pytest.fixture
            def failing_publisher(self):
                return MyPublisher(BrokenBackend())

            @pytest.fixture
            def delivered(self, backend):
                return lambda: len(backend.rows)
    """

    def test_every_event_kind_is_published_and_flushed(self, publisher, delivered):
        for kind in EventKind:
            publisher.publish(contract_event(kind))
        publisher.flush()

        assert delivered() == len(EventKind)

    def test_flush_on_an_empty_buffer_is_a_no_op(self, publisher, delivered):
        publisher.flush()
        publisher.flush()

        assert delivered() == 0

    def test_publish_after_flush_is_still_delivered(self, publisher, delivered):
        publisher.publish(contract_event(EventKind.RUN_START))
        publisher.flush()
        publisher.publish(contract_event(EventKind.RUN_END))
        publisher.flush()

        assert delivered() == 2

    @pytest.mark.parametrize("kind", _RUN_LEVEL, ids=_wire)
    def test_a_failed_run_level_publish_raises(self, failing_publisher, kind):
        # The run's state: losing it must fail the run.
        with pytest.raises(Exception):
            failing_publisher.publish(contract_event(kind))
            failing_publisher.flush()

    @pytest.mark.parametrize("kind", _AGGREGATE, ids=_wire)
    def test_a_failed_aggregate_publish_does_not_stop_the_run(self, failing_publisher, kind):
        # A counter: an audit hiccup must not halt ingestion.
        failing_publisher.publish(contract_event(kind))
        failing_publisher.flush()

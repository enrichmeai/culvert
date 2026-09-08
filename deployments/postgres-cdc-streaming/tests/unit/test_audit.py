"""PubSubAuditPublisher - the AD-5 failure split, and the wire shape.

What these tests guard
----------------------
The publisher they cover used to serialise with ``dataclasses.asdict`` and had
no failure handling at all: a Pub/Sub error either escaped uncaught or, at the
one call site, hit an ``except Exception: pass``. So the assertions here pin
the two facts that let an audit trail go unwritten while looking healthy:

1. the message carries exactly docs/CONTRACT.md section 4's ten columns, with
   an ``EventKind`` and a ``MappingProxyType`` payload that ``asdict`` could
   not have serialised at all;
2. a failed publish is never silent - run-level events raise, aggregate events
   log at ERROR and increment a counter, and ingestion continues.

The run-level / aggregate partition is written out below as two hardcoded
lists rather than read back from ``EventKind.is_run_level()``. That partition
*is* the contract; deriving it from the type under test would make this suite
agree with any future flip of it.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from data_pipeline_core.audit.events import CONTRACT_VERSION, AuditEvent, EventKind
from streaming_pipeline.pipeline.audit import PubSubAuditPublisher

PROJECT_ID = "my-project"
TOPIC_NAME = "generic-pipeline-events"
EVENT_TS = datetime(2026, 4, 17, 9, 14, tzinfo=timezone.utc)
EXTRACT_DATE = date(2026, 4, 16)

# docs/CONTRACT.md section 4, spine AD-5. Hardcoded on purpose - see the module
# docstring.
RUN_LEVEL_KINDS = [
    EventKind.RUN_START,
    EventKind.RUN_END,
    EventKind.ERROR_RAISED,
    EventKind.RECONCILIATION,
    EventKind.RETRY_ATTEMPTED,
]
AGGREGATE_KINDS = [
    EventKind.RECORD_VALIDATED,
    EventKind.RECORD_REJECTED,
]

# Minimal payload satisfying each kind's required keys.
_PAYLOADS = {
    EventKind.RUN_START: {"source_file": "pubsub://cdc-events"},
    EventKind.RUN_END: {"record_count": 7},
    EventKind.RECORD_VALIDATED: {"count": 7},
    EventKind.RECORD_REJECTED: {"count": 1, "quarantine_uri": "gs://b/q.json"},
    EventKind.RECONCILIATION: {
        "expected_count": 8, "accounted_count": 8, "reconciled": True,
    },
    EventKind.ERROR_RAISED: {
        "error_code": "RuntimeError", "error_category": "integration",
    },
    EventKind.RETRY_ATTEMPTED: {"attempt": 1, "previous_run_id": "run-0"},
}


class _FakeFuture:
    """A Pub/Sub publish future that either resolves or fails on result()."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.result_calls = 0

    def result(self, timeout: float | None = None):
        self.result_calls += 1
        if self._error is not None:
            raise self._error
        return "message-id-1"


class _FakePublisherClient:
    """Stands in for pubsub_v1.PublisherClient - no network, no credentials.

    ``publish_error`` fails synchronously (bad topic, auth, oversized message);
    ``future_error`` fails asynchronously, when the future is awaited. Both
    paths must obey the same AD-5 rule.
    """

    def __init__(self, publish_error: Exception | None = None,
                 future_error: Exception | None = None) -> None:
        self._publish_error = publish_error
        self._future_error = future_error
        self.calls: list[tuple[str, bytes, dict]] = []
        self.futures: list[_FakeFuture] = []

    def topic_path(self, project_id: str, topic_name: str) -> str:
        return f"projects/{project_id}/topics/{topic_name}"

    def publish(self, topic: str, data: bytes, **attributes):
        self.calls.append((topic, data, attributes))
        if self._publish_error is not None:
            raise self._publish_error
        future = _FakeFuture(self._future_error)
        self.futures.append(future)
        return future


def _event(kind: EventKind, **overrides) -> AuditEvent:
    kwargs = dict(
        run_id="20260417T091400Z-7f3a",
        system_id="postgres_cdc",
        entity="customers",
        event_kind=kind,
        event_ts=EVENT_TS,
        payload=_PAYLOADS[kind],
        extract_date=EXTRACT_DATE,
        producer="postgres-cdc-streaming@0.1.0",
        environment="int",
    )
    kwargs.update(overrides)
    return AuditEvent(**kwargs)


def _publisher(client: _FakePublisherClient) -> PubSubAuditPublisher:
    return PubSubAuditPublisher(
        project_id=PROJECT_ID, topic_name=TOPIC_NAME, publisher=client)


# --- wire shape: section 4's ten columns, nothing more ----------------------

def test_message_carries_exactly_the_ten_contract_columns() -> None:
    client = _FakePublisherClient()
    _publisher(client).publish(_event(EventKind.RUN_START))

    _, data, _ = client.calls[0]
    body = json.loads(data.decode("utf-8"))

    assert sorted(body) == sorted([
        "run_id", "system_id", "entity", "event_kind", "event_ts",
        "extract_date", "payload", "producer", "contract_version",
        "environment",
    ])
    assert body["event_kind"] == "RUN_START"
    assert body["event_ts"] == "2026-04-17T09:14:00+00:00"
    assert body["extract_date"] == "2026-04-16"
    assert body["payload"] == {"source_file": "pubsub://cdc-events"}
    assert body["contract_version"] == CONTRACT_VERSION


def test_retired_stage_summary_columns_are_gone() -> None:
    """The pre-0.2.0 AuditRecord shape must not survive anywhere on the wire."""
    client = _FakePublisherClient()
    _publisher(client).publish(_event(EventKind.RUN_END))

    body = json.loads(client.calls[0][1].decode("utf-8"))
    for retired in ("pipeline_name", "entity_type", "source_file",
                    "record_count", "processed_timestamp",
                    "processing_duration_seconds", "success", "error_count",
                    "audit_hash", "metadata"):
        assert retired not in body


def test_nullable_columns_are_bound_even_when_absent() -> None:
    """A stable wire shape: the keys are always present, the values may be null."""
    client = _FakePublisherClient()
    event = _event(EventKind.RUN_START, extract_date=None, producer=None,
                   environment=None)
    _publisher(client).publish(event)

    body = json.loads(client.calls[0][1].decode("utf-8"))
    assert body["extract_date"] is None
    assert body["producer"] is None
    assert body["environment"] is None


def test_contract_version_comes_from_the_event_not_the_constant() -> None:
    """A foreign producer's row round-trips with the version it was written against."""
    client = _FakePublisherClient()
    event = _event(EventKind.RUN_START, contract_version="9.9.9-foreign")
    _publisher(client).publish(event)

    body = json.loads(client.calls[0][1].decode("utf-8"))
    assert body["contract_version"] == "9.9.9-foreign"


def test_attributes_carry_the_event_identifiers() -> None:
    client = _FakePublisherClient()
    _publisher(client).publish(_event(EventKind.RUN_START))

    _, _, attributes = client.calls[0]
    assert attributes == {
        "run_id": "20260417T091400Z-7f3a",
        "entity": "customers",
        "event_kind": "RUN_START",
    }


# --- AD-5: run-level raises, aggregate does not, neither is silent ----------

@pytest.mark.parametrize("kind", RUN_LEVEL_KINDS, ids=lambda k: k.wire_value)
def test_failed_publish_of_a_run_level_event_raises(kind: EventKind) -> None:
    client = _FakePublisherClient(future_error=RuntimeError("Pub/Sub unavailable"))
    publisher = _publisher(client)

    with pytest.raises(RuntimeError) as excinfo:
        publisher.publish(_event(kind))

    assert kind.wire_value in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert str(excinfo.value.__cause__) == "Pub/Sub unavailable"
    assert publisher.audit_failure_count == 1


@pytest.mark.parametrize("kind", RUN_LEVEL_KINDS, ids=lambda k: k.wire_value)
def test_run_level_failure_raises_when_publish_fails_synchronously(
        kind: EventKind) -> None:
    """A bad topic or auth error fails at publish(), not at the future."""
    client = _FakePublisherClient(publish_error=ValueError("no such topic"))
    publisher = _publisher(client)

    with pytest.raises(RuntimeError):
        publisher.publish(_event(kind))

    assert publisher.audit_failure_count == 1


@pytest.mark.parametrize("kind", RUN_LEVEL_KINDS, ids=lambda k: k.wire_value)
def test_run_level_events_are_awaited_inline_not_deferred_to_flush(
        kind: EventKind) -> None:
    """The failure must surface at the call site, not at a flush that may never run.

    A run that dies before flushing would otherwise lose the failure entirely -
    the same swallow in a new place.
    """
    client = _FakePublisherClient()
    publisher = _publisher(client)

    publisher.publish(_event(kind))

    assert client.futures[0].result_calls == 1
    assert publisher._pending == []  # only aggregates are ever buffered


@pytest.mark.parametrize("kind", AGGREGATE_KINDS, ids=lambda k: k.wire_value)
def test_failed_publish_of_an_aggregate_event_does_not_raise(
        kind: EventKind, caplog: pytest.LogCaptureFixture) -> None:
    client = _FakePublisherClient(future_error=RuntimeError("Pub/Sub unavailable"))
    publisher = _publisher(client)

    with caplog.at_level(logging.ERROR):
        # A counter must not be able to halt ingestion.
        publisher.publish(_event(kind))
        publisher.flush()

    # But it is not swallowed either: the counter and the ERROR log are the
    # observables.
    assert publisher.audit_failure_count == 1
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert kind.wire_value in errors[0].getMessage()
    assert errors[0].exc_info is not None


@pytest.mark.parametrize("kind", AGGREGATE_KINDS, ids=lambda k: k.wire_value)
def test_aggregate_failure_is_reported_when_publish_fails_synchronously(
        kind: EventKind, caplog: pytest.LogCaptureFixture) -> None:
    client = _FakePublisherClient(publish_error=ValueError("no such topic"))
    publisher = _publisher(client)

    with caplog.at_level(logging.ERROR):
        publisher.publish(_event(kind))

    assert publisher.audit_failure_count == 1
    assert [r for r in caplog.records if r.levelno == logging.ERROR]


def test_aggregate_failures_accumulate_rather_than_vanishing(
        caplog: pytest.LogCaptureFixture) -> None:
    client = _FakePublisherClient(future_error=RuntimeError("Pub/Sub unavailable"))
    publisher = _publisher(client)

    with caplog.at_level(logging.ERROR):
        publisher.publish(_event(EventKind.RECORD_VALIDATED))
        publisher.publish(_event(EventKind.RECORD_VALIDATED))
        publisher.flush()

    assert publisher.audit_failure_count == 2
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


def test_nothing_is_logged_at_warning_and_left_at_that(
        caplog: pytest.LogCaptureFixture) -> None:
    """The exact defect being removed: WARN-and-continue on a failed append."""
    client = _FakePublisherClient(future_error=RuntimeError("Pub/Sub unavailable"))
    publisher = _publisher(client)

    with caplog.at_level(logging.DEBUG):
        publisher.publish(_event(EventKind.RECORD_VALIDATED))
        publisher.flush()
        with pytest.raises(RuntimeError):
            publisher.publish(_event(EventKind.RUN_END))

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_unserialisable_aggregate_payload_does_not_halt_ingestion(
        caplog: pytest.LogCaptureFixture) -> None:
    """AuditEvent validates payload *keys*, never value types.

    So a Decimal count reaches json.dumps and raises TypeError. That is a
    failed append like any other and must obey AD-5, not escape raw - an
    aggregate must not be able to halt ingestion by failing to serialise any
    more than by failing to send.
    """
    client = _FakePublisherClient()
    publisher = _publisher(client)
    event = _event(EventKind.RECORD_REJECTED,
                   payload={"count": Decimal(1), "quarantine_uri": "gs://b/q.json"})

    with caplog.at_level(logging.ERROR):
        publisher.publish(event)
        publisher.flush()

    assert client.calls == []  # never reached the wire
    assert publisher.audit_failure_count == 1
    assert [r for r in caplog.records if r.levelno == logging.ERROR]


def test_unserialisable_run_level_payload_raises() -> None:
    client = _FakePublisherClient()
    publisher = _publisher(client)
    event = _event(EventKind.RUN_END, payload={"record_count": Decimal(7)})

    with pytest.raises(RuntimeError) as excinfo:
        publisher.publish(event)

    assert "RUN_END" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, TypeError)
    assert publisher.audit_failure_count == 1


def test_audit_failure_count_is_zero_after_a_successful_publish() -> None:
    client = _FakePublisherClient()
    publisher = _publisher(client)

    publisher.publish(_event(EventKind.RUN_START))
    publisher.publish(_event(EventKind.RECORD_VALIDATED))
    publisher.flush()

    assert publisher.audit_failure_count == 0


# --- flush() ---------------------------------------------------------------

def test_flush_never_raises_because_only_aggregates_are_buffered() -> None:
    client = _FakePublisherClient(future_error=RuntimeError("Pub/Sub unavailable"))
    publisher = _publisher(client)

    publisher.publish(_event(EventKind.RECORD_REJECTED))
    publisher.flush()  # must not raise

    assert publisher.audit_failure_count == 1


def test_flush_on_an_empty_buffer_is_a_no_op() -> None:
    publisher = _publisher(_FakePublisherClient())

    publisher.flush()
    publisher.flush()

    assert publisher.audit_failure_count == 0


def test_flush_clears_the_buffer_so_a_second_flush_does_not_re_report() -> None:
    client = _FakePublisherClient()
    publisher = _publisher(client)

    publisher.publish(_event(EventKind.RECORD_VALIDATED))
    publisher.flush()
    publisher.flush()

    assert client.futures[0].result_calls == 1

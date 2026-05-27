"""Tests for PubSubSource / PubSubSink — no real Pub/Sub."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_gcp_pubsub import PubSubSink, PubSubSource


# --- PubSubSource ---------------------------------------------------------

def test_source_rejects_none_subscriber():
    with pytest.raises(TypeError):
        PubSubSource(None, "projects/p/subscriptions/s")


def test_source_rejects_none_subscription():
    with pytest.raises(TypeError):
        PubSubSource(MagicMock(), None)


def test_source_rejects_zero_max_messages():
    with pytest.raises(ValueError):
        PubSubSource(MagicMock(), "projects/p/subscriptions/s", max_messages=0)


def test_source_yields_messages_then_acks():
    subscriber = MagicMock()
    msg1 = MagicMock()
    msg1.data = b"payload-1"
    msg1.attributes = {"k": "v"}
    msg1.message_id = "id-1"
    msg1.publish_time = "2026-01-15T10:00:00Z"
    msg2 = MagicMock()
    msg2.data = b"payload-2"
    msg2.attributes = {}
    msg2.message_id = "id-2"
    msg2.publish_time = "2026-01-15T10:00:01Z"
    received1 = MagicMock()
    received1.message = msg1
    received1.ack_id = "ack-1"
    received2 = MagicMock()
    received2.message = msg2
    received2.ack_id = "ack-2"
    response = MagicMock()
    response.received_messages = [received1, received2]
    subscriber.pull.return_value = response

    source = PubSubSource(subscriber, "projects/p/subscriptions/s", max_messages=10)
    records = list(source.read())

    assert len(records) == 2
    assert records[0]["data"] == b"payload-1"
    assert records[0]["attributes"] == {"k": "v"}
    assert records[1]["message_id"] == "id-2"
    subscriber.acknowledge.assert_called_once()
    ack_call = subscriber.acknowledge.call_args
    assert ack_call.kwargs["request"]["ack_ids"] == ["ack-1", "ack-2"]


def test_source_empty_pull_no_ack():
    subscriber = MagicMock()
    response = MagicMock()
    response.received_messages = []
    subscriber.pull.return_value = response

    source = PubSubSource(subscriber, "projects/p/subscriptions/s")
    records = list(source.read())

    assert records == []
    subscriber.acknowledge.assert_not_called()


# --- PubSubSink -----------------------------------------------------------

def test_sink_rejects_none_publisher():
    with pytest.raises(TypeError):
        PubSubSink(None, "projects/p/topics/t")


def test_sink_rejects_none_topic():
    with pytest.raises(TypeError):
        PubSubSink(MagicMock(), None)


def test_sink_publishes_each_record_and_awaits_futures():
    publisher = MagicMock()
    future1 = MagicMock()
    future2 = MagicMock()
    publisher.publish.side_effect = [future1, future2]

    sink = PubSubSink(publisher, "projects/p/topics/t")
    sink.write(iter([
        {"data": b"msg-1", "attributes": {"k": "v"}},
        {"data": b"msg-2"},
    ]))

    assert publisher.publish.call_count == 2
    future1.result.assert_called_once()
    future2.result.assert_called_once()


def test_sink_rejects_record_without_data():
    publisher = MagicMock()
    sink = PubSubSink(publisher, "projects/p/topics/t")

    with pytest.raises(ValueError):
        sink.write(iter([{"attributes": {"k": "v"}}]))


def test_sink_empty_iterator_no_publish():
    publisher = MagicMock()
    sink = PubSubSink(publisher, "projects/p/topics/t")
    sink.write(iter([]))
    publisher.publish.assert_not_called()

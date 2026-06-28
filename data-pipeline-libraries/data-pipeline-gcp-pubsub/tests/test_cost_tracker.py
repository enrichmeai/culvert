"""Tests for PubSubCostTracker — no real Pub/Sub client.

End-to-end cost test re-derives one full cost:

    Publish: 1 TiB total_bytes (= BYTES_PER_TIB = 1_099_511_627_776 bytes)
    Formula (mirrors Java PubSubCostTracker.bytesToUsd, lines 182-186):
        estimatedCostUsd = total_bytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB
                         = 1_099_511_627_776 / 1_099_511_627_776 * 40.00
                         = 1.0 * 40.00
                         = 40.00 USD
"""

from __future__ import annotations

import pytest

from data_pipeline_gcp_pubsub.cost_tracker import (
    BYTES_PER_TIB,
    THROUGHPUT_COST_USD_PER_TIB,
    PubSubCostTracker,
    bytes_to_usd,
)
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics


# --- pricing constants -------------------------------------------------------

def test_bytes_per_tib_is_binary():
    """BYTES_PER_TIB must be exactly 2^40, not 1e12 (~10% difference matters)."""
    assert BYTES_PER_TIB == 2 ** 40
    assert BYTES_PER_TIB == 1_099_511_627_776


def test_throughput_cost_per_tib():
    assert THROUGHPUT_COST_USD_PER_TIB == 40.00


# --- end-to-end cost formula -------------------------------------------------

def test_bytes_to_usd_one_tib():
    """Re-derive: 1 TiB publish → $40.00.

    Mirrors Java PubSubCostTracker.bytesToUsd (lines 182-186):
        return (double) bytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;

    Input:  bytes = BYTES_PER_TIB = 1_099_511_627_776
    Rate:   THROUGHPUT_COST_USD_PER_TIB = 40.00
    Output: 1_099_511_627_776 / 1_099_511_627_776 * 40.00 = 40.00 USD
    """
    result = bytes_to_usd(BYTES_PER_TIB)
    assert result == pytest.approx(40.00)


def test_bytes_to_usd_half_tib():
    """0.5 TiB → $20.00."""
    result = bytes_to_usd(BYTES_PER_TIB // 2)
    assert result == pytest.approx(20.00)


def test_bytes_to_usd_zero():
    assert bytes_to_usd(0) == 0.0


def test_bytes_to_usd_negative():
    assert bytes_to_usd(-1) == 0.0


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def tag():
    return FinOpsTag(
        system="culvert", environment="test", cost_center="eng",
        owner="team", run_id="run-pubsub",
    )


@pytest.fixture
def recording_sink():
    records = []

    class _RecordingSink:
        def record(self, metrics, tags):
            records.append((metrics, tags))

    sink = _RecordingSink()
    sink.records = records
    return sink


@pytest.fixture
def tracker(recording_sink):
    return PubSubCostTracker(recording_sink)


# --- constructor guard -------------------------------------------------------

def test_rejects_none_sink():
    with pytest.raises(TypeError):
        PubSubCostTracker(None)


# --- track_publish -----------------------------------------------------------

def test_track_publish_rejects_none_run_id(tracker, tag):
    with pytest.raises(TypeError):
        tracker.track_publish(100, 1024, None, tag)


def test_track_publish_rejects_none_tag(tracker):
    with pytest.raises(TypeError):
        tracker.track_publish(100, 1024, "r1", None)


def test_track_publish_one_tib(recording_sink, tag):
    """End-to-end: 1 TiB publish → $40.00 emitted to sink."""
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_publish(1_000_000, BYTES_PER_TIB, "run-pubsub", tag)

    assert len(recording_sink.records) == 1
    m, t = recording_sink.records[0]
    assert m.billed_messages_count == 1_000_000
    assert m.billed_bytes_written == BYTES_PER_TIB
    assert m.estimated_cost_usd == pytest.approx(40.00)
    assert t is tag


def test_track_publish_zero_bytes_emits_zero_cost(recording_sink, tag):
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_publish(100, 0, "r1", tag)
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_written == 0
    assert m.estimated_cost_usd == pytest.approx(0.0)


def test_track_publish_zero_messages_still_calls_sink(recording_sink, tag):
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_publish(0, 1024, "r1", tag)
    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.billed_messages_count == 0


def test_track_publish_negative_bytes_treated_as_zero(recording_sink, tag):
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_publish(10, -500, "r1", tag)
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_written == 0
    assert m.estimated_cost_usd == pytest.approx(0.0)


# --- track_subscribe ---------------------------------------------------------

def test_track_subscribe_rejects_none_run_id(tracker, tag):
    with pytest.raises(TypeError):
        tracker.track_subscribe(100, 1024, None, tag)


def test_track_subscribe_rejects_none_tag(tracker):
    with pytest.raises(TypeError):
        tracker.track_subscribe(100, 1024, "r1", None)


def test_track_subscribe_one_tib(recording_sink, tag):
    """End-to-end: 1 TiB subscribe → $40.00 emitted to sink."""
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_subscribe(500_000, BYTES_PER_TIB, "run-sub", tag)

    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.billed_messages_count == 500_000
    assert m.billed_bytes_written == BYTES_PER_TIB
    assert m.estimated_cost_usd == pytest.approx(40.00)


def test_track_subscribe_zero_bytes(recording_sink, tag):
    tracker = PubSubCostTracker(recording_sink)
    tracker.track_subscribe(10, 0, "r1", tag)
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.0)

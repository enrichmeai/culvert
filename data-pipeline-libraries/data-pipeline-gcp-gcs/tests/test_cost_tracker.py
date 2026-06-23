"""Tests for GcsCostTracker — no real GCS client.

End-to-end cost test re-derives one full cost:

    Upload: 1 GiB written (= BYTES_PER_GIB = 1_073_741_824 bytes)
    Formula (mirrors Java GcsCostTracker.bytesToUsd, lines 244-248):
        estimatedCostUsd = bytes / BYTES_PER_GIB * WRITE_COST_USD_PER_GIB
                         = 1_073_741_824 / 1_073_741_824 * 0.01
                         = 1.0 * 0.01
                         = 0.01 USD
"""

from __future__ import annotations

import pytest

from data_pipeline_gcp_gcs.cost_tracker import (
    ARCHIVE_STORAGE_USD_PER_GIB,
    BYTES_PER_GIB,
    COLDLINE_STORAGE_USD_PER_GIB,
    NEARLINE_STORAGE_USD_PER_GIB,
    STANDARD_STORAGE_USD_PER_GIB,
    WRITE_COST_USD_PER_GIB,
    GcsCostTracker,
    bytes_to_usd,
)
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics


# --- pricing constants -------------------------------------------------------

def test_bytes_per_gib_is_binary():
    """BYTES_PER_GIB must be exactly 2^30, not 1e9 (~7% difference matters)."""
    assert BYTES_PER_GIB == 2 ** 30
    assert BYTES_PER_GIB == 1_073_741_824


def test_write_cost_per_gib():
    assert WRITE_COST_USD_PER_GIB == 0.01


def test_standard_storage_rate():
    assert STANDARD_STORAGE_USD_PER_GIB == 0.020


def test_nearline_storage_rate():
    assert NEARLINE_STORAGE_USD_PER_GIB == 0.010


def test_coldline_storage_rate():
    assert COLDLINE_STORAGE_USD_PER_GIB == 0.004


def test_archive_storage_rate():
    assert ARCHIVE_STORAGE_USD_PER_GIB == 0.0012


# --- end-to-end cost formula -------------------------------------------------

def test_bytes_to_usd_one_gib_upload():
    """Re-derive: 1 GiB upload → $0.01.

    Mirrors Java GcsCostTracker.bytesToUsd (lines 244-248):
        return (double) bytes / (double) BYTES_PER_GIB * ratePerGib;

    Input:  bytes = BYTES_PER_GIB = 1_073_741_824
    Rate:   WRITE_COST_USD_PER_GIB = 0.01
    Output: 1_073_741_824 / 1_073_741_824 * 0.01 = 0.01 USD
    """
    result = bytes_to_usd(BYTES_PER_GIB, WRITE_COST_USD_PER_GIB)
    assert result == pytest.approx(0.01)


def test_bytes_to_usd_one_gib_standard_storage():
    """1 GiB STANDARD → $0.020/GiB-month."""
    result = bytes_to_usd(BYTES_PER_GIB, STANDARD_STORAGE_USD_PER_GIB)
    assert result == pytest.approx(0.020)


def test_bytes_to_usd_two_gib_coldline():
    """2 GiB COLDLINE → 2 * $0.004 = $0.008/GiB-month."""
    result = bytes_to_usd(2 * BYTES_PER_GIB, COLDLINE_STORAGE_USD_PER_GIB)
    assert result == pytest.approx(0.008)


def test_bytes_to_usd_zero():
    assert bytes_to_usd(0, WRITE_COST_USD_PER_GIB) == 0.0


def test_bytes_to_usd_negative():
    assert bytes_to_usd(-1, WRITE_COST_USD_PER_GIB) == 0.0


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def tag():
    return FinOpsTag(
        system="culvert", environment="test", cost_center="eng",
        owner="team", run_id="run-gcs",
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
    return GcsCostTracker(recording_sink)


# --- constructor guard -------------------------------------------------------

def test_rejects_none_sink():
    with pytest.raises(TypeError):
        GcsCostTracker(None)


# --- track_upload ------------------------------------------------------------

def test_track_upload_rejects_none_run_id(tracker, tag):
    with pytest.raises(TypeError):
        tracker.track_upload(1024, None, tag)


def test_track_upload_rejects_none_tag(tracker):
    with pytest.raises(TypeError):
        tracker.track_upload(1024, "r1", None)


def test_track_upload_one_gib(recording_sink, tag):
    """End-to-end: 1 GiB upload → $0.01 emitted to sink."""
    tracker = GcsCostTracker(recording_sink)
    tracker.track_upload(BYTES_PER_GIB, "run-gcs", tag)

    assert len(recording_sink.records) == 1
    m, t = recording_sink.records[0]
    assert m.billed_bytes_written == BYTES_PER_GIB
    assert m.estimated_cost_usd == pytest.approx(0.01)
    assert t is tag


def test_track_upload_zero_bytes_emits_zero_cost(recording_sink, tag):
    """Zero bytes: sink still called once; cost is 0."""
    tracker = GcsCostTracker(recording_sink)
    tracker.track_upload(0, "r1", tag)

    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_written == 0
    assert m.estimated_cost_usd == pytest.approx(0.0)


def test_track_upload_negative_bytes_treated_as_zero(recording_sink, tag):
    tracker = GcsCostTracker(recording_sink)
    tracker.track_upload(-100, "r1", tag)
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_written == 0


# --- track_storage_class -----------------------------------------------------

def test_track_storage_class_rejects_none_run_id(tracker, tag):
    with pytest.raises(TypeError):
        tracker.track_storage_class(1024, "STANDARD", None, tag)


def test_track_storage_class_rejects_none_tag(tracker):
    with pytest.raises(TypeError):
        tracker.track_storage_class(1024, "STANDARD", "r1", None)


def test_track_storage_class_standard(recording_sink, tag):
    """1 GiB STANDARD → $0.020."""
    tracker = GcsCostTracker(recording_sink)
    tracker.track_storage_class(BYTES_PER_GIB, "STANDARD", "run-gcs", tag)

    m, _ = recording_sink.records[0]
    assert m.billed_bytes_stored == BYTES_PER_GIB
    assert m.estimated_cost_usd == pytest.approx(0.020)


def test_track_storage_class_nearline(recording_sink, tag):
    """1 GiB NEARLINE → $0.010."""
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, "NEARLINE", "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.010)


def test_track_storage_class_coldline(recording_sink, tag):
    """1 GiB COLDLINE → $0.004."""
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, "COLDLINE", "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.004)


def test_track_storage_class_archive(recording_sink, tag):
    """1 GiB ARCHIVE → $0.0012."""
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, "ARCHIVE", "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.0012)


def test_track_storage_class_case_insensitive(recording_sink, tag):
    """'standard' (lowercase) resolves to STANDARD rate."""
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, "standard", "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.020)


def test_track_storage_class_unknown_falls_back_to_standard(recording_sink, tag):
    """Unknown storage class falls back to Standard rate, logs WARN."""
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, "GLACIER", "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.020)


def test_track_storage_class_none_falls_back_to_standard(recording_sink, tag):
    GcsCostTracker(recording_sink).track_storage_class(
        BYTES_PER_GIB, None, "r1", tag
    )
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.020)


def test_track_storage_class_zero_bytes(recording_sink, tag):
    """Zero bytes still calls sink once with zero cost."""
    GcsCostTracker(recording_sink).track_storage_class(0, "STANDARD", "r1", tag)
    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_stored == 0
    assert m.estimated_cost_usd == pytest.approx(0.0)

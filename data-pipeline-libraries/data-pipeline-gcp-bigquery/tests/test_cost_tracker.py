"""Tests for BigQueryCostTracker — no real BigQuery client.

End-to-end cost test re-derives one full cost:

    Query: 1 TiB scanned (= BYTES_PER_TIB = 1_099_511_627_776 bytes)
    Formula (mirrors Java BigQueryCostTracker.bytesToUsd, lines 321-326):
        estimatedCostUsd = bytes / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB
                         = 1_099_511_627_776 / 1_099_511_627_776 * 5.00
                         = 1.0 * 5.00
                         = 5.00 USD
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_gcp_bigquery.cost_tracker import (
    BYTES_PER_TIB,
    LOAD_COST_USD_PER_TIB,
    QUERY_COST_USD_PER_TIB,
    BigQueryCostTracker,
    bytes_to_usd,
)
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics


# --- pricing constants -------------------------------------------------------

def test_bytes_per_tib_is_binary():
    """BYTES_PER_TIB must be exactly 2^40, not 1e12 (10% difference matters)."""
    assert BYTES_PER_TIB == 2 ** 40
    assert BYTES_PER_TIB == 1_099_511_627_776


def test_query_cost_per_tib():
    assert QUERY_COST_USD_PER_TIB == 5.00


def test_load_cost_per_tib():
    assert LOAD_COST_USD_PER_TIB == 0.01


# --- end-to-end cost formula -------------------------------------------------

def test_bytes_to_usd_one_tib_query():
    """Re-derive: 1 TiB query → $5.00.

    Mirrors Java BigQueryCostTracker.bytesToUsd (lines 321-326):
        return (double) bytes / (double) BYTES_PER_TIB * costPerTib;

    Input:  bytes = BYTES_PER_TIB = 1_099_511_627_776
    Rate:   QUERY_COST_USD_PER_TIB = 5.00
    Output: 1_099_511_627_776 / 1_099_511_627_776 * 5.00 = 5.00 USD
    """
    result = bytes_to_usd(BYTES_PER_TIB, QUERY_COST_USD_PER_TIB)
    assert result == pytest.approx(5.00)


def test_bytes_to_usd_one_tib_load():
    """Re-derive: 1 TiB load → $0.01.

    Input:  bytes = BYTES_PER_TIB = 1_099_511_627_776
    Rate:   LOAD_COST_USD_PER_TIB = 0.01
    Output: 1_099_511_627_776 / 1_099_511_627_776 * 0.01 = 0.01 USD
    """
    result = bytes_to_usd(BYTES_PER_TIB, LOAD_COST_USD_PER_TIB)
    assert result == pytest.approx(0.01)


def test_bytes_to_usd_half_tib():
    """Half TiB query → $2.50."""
    result = bytes_to_usd(BYTES_PER_TIB // 2, QUERY_COST_USD_PER_TIB)
    assert result == pytest.approx(2.50)


def test_bytes_to_usd_zero():
    assert bytes_to_usd(0, QUERY_COST_USD_PER_TIB) == 0.0


def test_bytes_to_usd_negative():
    assert bytes_to_usd(-1, QUERY_COST_USD_PER_TIB) == 0.0


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def tag():
    return FinOpsTag(
        system="culvert", environment="test", cost_center="eng",
        owner="team", run_id="run-42",
    )


@pytest.fixture
def recording_sink():
    """Captures the CostMetrics passed to record()."""
    records = []

    class _RecordingSink:
        def record(self, metrics, tags):
            records.append((metrics, tags))

    sink = _RecordingSink()
    sink.records = records
    return sink


@pytest.fixture
def tracker(recording_sink):
    return BigQueryCostTracker(MagicMock(), recording_sink)


# --- constructor guards ------------------------------------------------------

def test_rejects_none_client():
    with pytest.raises(TypeError):
        BigQueryCostTracker(None, MagicMock())


def test_rejects_none_sink():
    with pytest.raises(TypeError):
        BigQueryCostTracker(MagicMock(), None)


# --- track_job guards --------------------------------------------------------

def test_track_job_rejects_none_job(tracker, tag):
    with pytest.raises(TypeError):
        tracker.track_job(None, "r1", tag)


def test_track_job_rejects_none_run_id(tracker, tag):
    job = MagicMock()
    job._job_statistics.return_value = None
    with pytest.raises(TypeError):
        tracker.track_job(job, None, tag)


def test_track_job_rejects_none_tag(tracker):
    job = MagicMock()
    with pytest.raises(TypeError):
        tracker.track_job(job, "r1", None)


# --- query job ---------------------------------------------------------------

def test_track_job_query_populates_cost(recording_sink, tag):
    """Full end-to-end: 1 TiB query → $5.00 in the emitted CostMetrics."""
    stats = MagicMock()
    stats.job_type = "QUERY"
    stats.total_bytes_billed = BYTES_PER_TIB  # 1 TiB
    stats.total_slot_ms = 1000

    job = MagicMock()
    job._job_statistics.return_value = stats

    tracker = BigQueryCostTracker(MagicMock(), recording_sink)
    tracker.track_job(job, "run-42", tag)

    assert len(recording_sink.records) == 1
    m, t = recording_sink.records[0]
    assert m.billed_bytes_scanned == BYTES_PER_TIB
    assert m.slot_millis == 1000
    assert m.estimated_cost_usd == pytest.approx(5.00)


def test_track_job_query_null_bytes_treated_as_zero(recording_sink, tag):
    stats = MagicMock()
    stats.job_type = "QUERY"
    stats.total_bytes_billed = None
    stats.total_slot_ms = 500

    job = MagicMock()
    job._job_statistics.return_value = stats

    tracker = BigQueryCostTracker(MagicMock(), recording_sink)
    tracker.track_job(job, "r1", tag)

    m, _ = recording_sink.records[0]
    assert m.billed_bytes_scanned == 0
    assert m.estimated_cost_usd == pytest.approx(0.0)


# --- load job ----------------------------------------------------------------

def test_track_job_load_populates_cost(recording_sink, tag):
    """Full end-to-end: 1 TiB load → $0.01 in emitted CostMetrics."""
    stats = MagicMock()
    stats.job_type = "LOAD"
    stats.output_bytes = BYTES_PER_TIB  # 1 TiB

    job = MagicMock()
    job._job_statistics.return_value = stats

    tracker = BigQueryCostTracker(MagicMock(), recording_sink)
    tracker.track_job(job, "run-load", tag)

    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.billed_bytes_written == BYTES_PER_TIB
    assert m.estimated_cost_usd == pytest.approx(0.01)


# --- null statistics ---------------------------------------------------------

def test_track_job_null_stats_skips_emission(recording_sink, tag):
    job = MagicMock()
    job._job_statistics.return_value = None

    tracker = BigQueryCostTracker(MagicMock(), recording_sink)
    tracker.track_job(job, "r1", tag)
    assert len(recording_sink.records) == 0


# --- other job type (copy/export/script) ------------------------------------

def test_track_job_other_type_zero_cost(recording_sink, tag):
    stats = MagicMock(spec=[])  # no attributes like total_bytes_billed/output_bytes
    stats.job_type = "COPY"

    job = MagicMock()
    job._job_statistics.return_value = stats

    tracker = BigQueryCostTracker(MagicMock(), recording_sink)
    tracker.track_job(job, "r1", tag)
    assert len(recording_sink.records) == 1
    m, _ = recording_sink.records[0]
    assert m.estimated_cost_usd == pytest.approx(0.0)

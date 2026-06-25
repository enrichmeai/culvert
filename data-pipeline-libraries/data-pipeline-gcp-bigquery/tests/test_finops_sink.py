"""Tests for BigQueryFinOpsSink — no real BigQuery client."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from data_pipeline_gcp_bigquery import BigQueryFinOpsSink, FinOpsInsertException
from data_pipeline_core.finops_api.models import CostMetrics
from data_pipeline_core.finops_api.labels import FinOpsTag


# --- fixtures ---------------------------------------------------------------

@pytest.fixture
def tag():
    return FinOpsTag(
        system="culvert",
        environment="test",
        cost_center="engineering",
        owner="team-data",
        run_id="run-001",
        extra={"team": "data-platform"},
    )


@pytest.fixture
def metrics():
    return CostMetrics(
        run_id="run-001",
        estimated_cost_usd=1.23,
        billed_bytes_scanned=1_099_511_627_776,  # 1 TiB
        slot_millis=500,
        labels={"env": "test"},
    )


@pytest.fixture
def client():
    c = MagicMock()
    c.insert_rows_json.return_value = []  # success: empty error list
    return c


@pytest.fixture
def sink(client):
    return BigQueryFinOpsSink(client, "my-project", "finops_ds", "cost_metrics")


# --- constructor guards ------------------------------------------------------

def test_rejects_none_client():
    with pytest.raises(TypeError):
        BigQueryFinOpsSink(None, "p", "ds", "t")


def test_rejects_none_project():
    with pytest.raises(TypeError):
        BigQueryFinOpsSink(MagicMock(), None, "ds", "t")


def test_rejects_none_dataset():
    with pytest.raises(TypeError):
        BigQueryFinOpsSink(MagicMock(), "p", None, "t")


def test_rejects_none_table():
    with pytest.raises(TypeError):
        BigQueryFinOpsSink(MagicMock(), "p", "ds", None)


# --- record() guards --------------------------------------------------------

def test_record_rejects_none_metrics(sink, tag):
    with pytest.raises(TypeError):
        sink.record(None, tag)


def test_record_rejects_none_tags(sink, metrics):
    with pytest.raises(TypeError):
        sink.record(metrics, None)


# --- happy path --------------------------------------------------------------

def test_record_calls_insert_rows_json(sink, client, metrics, tag):
    sink.record(metrics, tag)
    client.insert_rows_json.assert_called_once()
    table_ref, rows = client.insert_rows_json.call_args.args
    assert table_ref == "my-project.finops_ds.cost_metrics"
    assert len(rows) == 1


def test_record_row_contains_finops_tag_fields(sink, client, metrics, tag):
    sink.record(metrics, tag)
    row = client.insert_rows_json.call_args.args[1][0]
    assert row["system"] == "culvert"
    assert row["environment"] == "test"
    assert row["cost_center"] == "engineering"
    assert row["owner"] == "team-data"
    assert row["tag_run_id"] == "run-001"
    # extra should be flattened to [{"key": "team", "value": "data-platform"}]
    assert row["tag_extra"] == [{"key": "team", "value": "data-platform"}]


def test_record_row_contains_cost_metrics_fields(sink, client, metrics, tag):
    sink.record(metrics, tag)
    row = client.insert_rows_json.call_args.args[1][0]
    assert row["run_id"] == "run-001"
    assert row["estimated_cost_usd"] == pytest.approx(1.23)
    assert row["billed_bytes_scanned"] == 1_099_511_627_776
    assert row["slot_millis"] == 500
    # labels: {"env": "test"} → [{"key": "env", "value": "test"}]
    assert row["labels"] == [{"key": "env", "value": "test"}]
    assert "timestamp" in row


def test_record_row_empty_labels_and_extra(client):
    m = CostMetrics(run_id="r1")
    t = FinOpsTag(
        system="s", environment="e", cost_center="c", owner="o", run_id="r1"
    )
    sink = BigQueryFinOpsSink(client, "p", "ds", "t")
    sink.record(m, t)
    row = client.insert_rows_json.call_args.args[1][0]
    assert row["labels"] == []
    assert row["tag_extra"] == []


# --- error path --------------------------------------------------------------

def test_record_raises_on_insert_errors(client, metrics, tag):
    client.insert_rows_json.return_value = [{"index": 0, "errors": [{"reason": "invalid"}]}]
    sink = BigQueryFinOpsSink(client, "p", "ds", "t")
    with pytest.raises(FinOpsInsertException) as exc_info:
        sink.record(metrics, tag)
    assert "run-001" in str(exc_info.value)


def test_finops_insert_exception_carries_errors():
    errors = [{"index": 0, "errors": [{"reason": "stopped"}]}]
    exc = FinOpsInsertException("r42", errors)
    assert exc.run_id == "r42"
    assert exc.insert_errors is errors
    assert "r42" in str(exc)


# --- default table constant --------------------------------------------------

def test_default_table_constant():
    from data_pipeline_gcp_bigquery.finops_sink import DEFAULT_TABLE
    assert DEFAULT_TABLE == "cost_metrics"


def test_default_table_used_when_not_specified(client, metrics, tag):
    sink = BigQueryFinOpsSink(client, "p", "ds")
    sink.record(metrics, tag)
    table_ref = client.insert_rows_json.call_args.args[0]
    assert table_ref.endswith(".cost_metrics")

"""Tests for FDP readiness check."""

from unittest.mock import MagicMock

import pytest
from fdp_trigger.readiness import check_fdp_ready, ReadinessResult


def _mock_row(table_name, partition_id, total_rows, quiet_minutes):
    """Build a fake BigQuery row."""
    row = MagicMock()
    row.table_name = table_name
    row.partition_id = partition_id
    row.total_rows = total_rows
    row.quiet_minutes = quiet_minutes
    return row


def _mock_client(rows):
    """Build a mock BigQuery client that returns the given rows."""
    client = MagicMock()
    query_job = MagicMock()
    query_job.result.return_value = iter(rows)
    client.query.return_value = query_job
    return client


def test_all_tables_ready():
    rows = [
        _mock_row("event_txn", "20260409", 1000, 20),
        _mock_row("portfolio", "20260409", 500, 18),
        _mock_row("facility", "20260409", 200, 30),
    ]
    client = _mock_client(rows)
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=("event_txn", "portfolio", "facility"),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is True
    assert "stable" in result.reason
    assert len(result.partitions) == 3


def test_missing_table_not_ready():
    rows = [
        _mock_row("event_txn", "20260409", 1000, 20),
        # missing portfolio and facility
    ]
    client = _mock_client(rows)
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=("event_txn", "portfolio", "facility"),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is False
    assert "not found" in result.reason
    assert "portfolio" in result.reason
    assert "facility" in result.reason


def test_zero_rows_not_ready():
    rows = [
        _mock_row("event_txn", "20260409", 1000, 20),
        _mock_row("portfolio", "20260409", 0, 20),  # empty partition
        _mock_row("facility", "20260409", 200, 20),
    ]
    client = _mock_client(rows)
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=("event_txn", "portfolio", "facility"),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is False
    assert "zero rows" in result.reason
    assert "portfolio" in result.reason


def test_unstable_not_ready():
    rows = [
        _mock_row("event_txn", "20260409", 1000, 20),
        _mock_row("portfolio", "20260409", 500, 5),  # still being written
        _mock_row("facility", "20260409", 200, 20),
    ]
    client = _mock_client(rows)
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=("event_txn", "portfolio", "facility"),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is False
    assert "still being written" in result.reason


def test_exact_stability_boundary_is_ready():
    """quiet_minutes == stability_minutes should be considered stable."""
    rows = [
        _mock_row("event_txn", "20260409", 1000, 15),
    ]
    client = _mock_client(rows)
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=("event_txn",),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is True


def test_empty_table_list_not_ready():
    client = _mock_client([])
    result = check_fdp_ready(
        client=client,
        fdp_project="other-project",
        fdp_dataset="fdp_dataset",
        fdp_tables=(),
        extract_date="2026-04-09",
        stability_minutes=15,
    )
    assert result.is_ready is False
    assert "No FDP tables configured" in result.reason

"""Unit tests for SplitFileHandler."""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock

import pytest

from gcp_pipeline_beam.file_management.split_file_handler import (
    SplitFileHandler,
    SplitFileSet,
    SplitFileTimeoutError,
)


def _fake_gcs(objects: List[str]) -> MagicMock:
    """Return a mock GCSClient whose list_blobs yields the given object names."""
    gcs = MagicMock()
    gcs.list_blobs = MagicMock(
        side_effect=lambda bucket, prefix="": [o for o in objects if o.startswith(prefix)]
    )
    return gcs


def test_scan_returns_empty_set_when_no_objects():
    gcs = _fake_gcs(objects=[])
    handler = SplitFileHandler(bucket="landing", gcs_client=gcs)

    result = handler.scan(prefix="customers", extract_date="20260417")

    assert isinstance(result, SplitFileSet)
    assert result.total_parts == 0
    assert not result.complete


def test_scan_detects_ready_when_all_ok_files_present():
    objects = [
        "customers.20260417.001of003.csv",
        "customers.20260417.002of003.csv",
        "customers.20260417.003of003.csv",
        "customers.20260417.001of003.ok",
        "customers.20260417.002of003.ok",
        "customers.20260417.003of003.ok",
    ]
    handler = SplitFileHandler(bucket="landing", gcs_client=_fake_gcs(objects))

    result = handler.scan(prefix="customers", extract_date="20260417")

    assert result.total_parts == 3
    assert len(result.parts) == 3
    assert [p.part_number for p in result.parts] == [1, 2, 3]
    assert all(p.is_ready for p in result.parts)
    assert result.complete
    assert result.uris == tuple(
        f"gs://landing/customers.20260417.{n:03d}of003.csv" for n in (1, 2, 3)
    )


def test_scan_marks_parts_not_ready_without_ok_sentinel():
    objects = [
        "customers.20260417.001of002.csv",
        "customers.20260417.002of002.csv",
        "customers.20260417.001of002.ok",
        # Missing .ok for part 2
    ]
    handler = SplitFileHandler(bucket="landing", gcs_client=_fake_gcs(objects))

    result = handler.scan(prefix="customers", extract_date="20260417")

    assert result.total_parts == 2
    assert result.parts[0].is_ready
    assert not result.parts[1].is_ready
    assert not result.complete


def test_scan_ignores_non_matching_filenames():
    objects = [
        "customers.20260417.001of001.csv",
        "customers.20260417.001of001.ok",
        "customers.20260417.summary.txt",            # different suffix
        "customers.20260418.001of001.csv",           # wrong date
        "accounts.20260417.001of001.csv",            # wrong prefix
    ]
    handler = SplitFileHandler(bucket="landing", gcs_client=_fake_gcs(objects))

    result = handler.scan(prefix="customers", extract_date="20260417")

    assert result.total_parts == 1
    assert len(result.parts) == 1
    assert result.parts[0].part_number == 1


def test_wait_times_out_when_parts_do_not_arrive():
    objects = [
        "customers.20260417.001of002.csv",
        # Only part 1; part 2 never arrives.
    ]
    handler = SplitFileHandler(
        bucket="landing",
        gcs_client=_fake_gcs(objects),
        poll_interval_seconds=0.01,
    )

    with pytest.raises(SplitFileTimeoutError):
        handler.wait_for_complete_set(
            prefix="customers", extract_date="20260417", timeout_seconds=0.05,
        )


def test_wait_returns_when_parts_complete_between_polls():
    state = {"objects": ["customers.20260417.001of002.csv"]}

    def list_blobs(bucket, prefix=""):
        return [o for o in state["objects"] if o.startswith(prefix)]

    gcs = MagicMock()
    gcs.list_blobs = MagicMock(side_effect=list_blobs)
    handler = SplitFileHandler(
        bucket="landing", gcs_client=gcs, poll_interval_seconds=0.0,
    )

    # Seed full completion just before the second poll.
    def complete_set(*_args, **_kwargs):
        state["objects"] = [
            "customers.20260417.001of002.csv",
            "customers.20260417.002of002.csv",
            "customers.20260417.001of002.ok",
            "customers.20260417.002of002.ok",
        ]
        return [o for o in state["objects"] if o.startswith(_kwargs.get("prefix", ""))]

    # First call returns incomplete; subsequent calls return complete.
    call_count = {"n": 0}

    def progressive(bucket, prefix=""):
        call_count["n"] += 1
        if call_count["n"] >= 3:
            state["objects"] = [
                "customers.20260417.001of002.csv",
                "customers.20260417.002of002.csv",
                "customers.20260417.001of002.ok",
                "customers.20260417.002of002.ok",
            ]
        return [o for o in state["objects"] if o.startswith(prefix)]

    gcs.list_blobs = MagicMock(side_effect=progressive)

    result = handler.wait_for_complete_set(
        prefix="customers", extract_date="20260417", timeout_seconds=2.0,
    )

    assert result.complete
    assert result.total_parts == 2

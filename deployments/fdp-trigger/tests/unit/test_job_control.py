"""Tests for the job_control writer.

Two things must hold and neither is visible from the return value, so both are
asserted against the SQL and its parameters:

1. The row is written with DML, not the streaming insert API. A streamed row is
   invisible to the Dataflow job's terminal ``UPDATE`` until the streaming
   buffer flushes, which would leave the row ``running`` forever.
2. The status is Culvert's lowercase ``running`` (AD-17), and the columns are
   the authoritative ``pipeline_jobs`` shape the Java port reads.
"""

from unittest.mock import MagicMock

import pytest

from fdp_trigger.job_control import STATUS_ON_LAUNCH, record_trigger

TABLE = "proj.job_control.pipeline_jobs"
SOURCE_FILES = ["fdp:ds.event_txn", "fdp:ds.portfolio"]


def _mock_client(affected_rows=1):
    client = MagicMock()
    query_job = MagicMock()
    query_job.num_dml_affected_rows = affected_rows
    client.query.return_value = query_job
    return client


def _record(client):
    record_trigger(
        client=client,
        job_control_table=TABLE,
        run_id="auto_20260409_123456",
        segment="customer",
        extract_date="2026-04-09",
        source_files=SOURCE_FILES,
    )


def _params(client):
    job_config = client.query.call_args.kwargs["job_config"]
    return {p.name: p.value for p in job_config.query_parameters}


def test_writes_lowercase_running_status():
    client = _mock_client()
    _record(client)
    assert _params(client)["status"] == "running"
    assert STATUS_ON_LAUNCH == "running"


def test_does_not_write_the_dead_uppercase_vocabulary():
    client = _mock_client()
    _record(client)
    sql = client.query.call_args.args[0]
    assert "RUNNING" not in sql
    assert "SUCCESS" not in sql
    assert _params(client)["status"] != "RUNNING"


def test_uses_dml_insert_not_the_streaming_api():
    """
    insert_rows_json rows sit in the streaming buffer and cannot be UPDATEd,
    so the Dataflow job could never write the terminal status.
    """
    client = _mock_client()
    _record(client)
    client.insert_rows_json.assert_not_called()
    client.query.assert_called_once()
    assert "INSERT INTO" in client.query.call_args.args[0]


def test_writes_the_authoritative_pipeline_jobs_columns():
    """
    Matches infrastructure/terraform/systems/generic/main.tf's pipeline_jobs
    schema and BigQueryJobControlRepository#createJob's column list -- notably
    source_file (singular STRING), not the predecessor's REPEATED source_files.
    """
    client = _mock_client()
    _record(client)
    sql = client.query.call_args.args[0]
    for column in (
        "run_id", "system_id", "pipeline_name", "extract_date", "status",
        "job_type", "entity_type", "source_file", "created_at", "updated_at",
        "started_at",
    ):
        assert column in sql, f"missing column {column}"
    assert "source_files" not in sql
    assert _params(client)["source_file"] == ",".join(SOURCE_FILES)


def test_stamps_created_at_the_partition_column():
    client = _mock_client()
    _record(client)
    sql = client.query.call_args.args[0]
    assert "CURRENT_TIMESTAMP()" in sql


def test_raises_when_the_insert_affects_no_rows():
    """A write that moved nothing must fail loudly, never be assumed good."""
    client = _mock_client(affected_rows=0)
    with pytest.raises(RuntimeError, match="affected 0 rows"):
        _record(client)


def test_raises_when_the_affected_row_count_is_unavailable():
    client = _mock_client(affected_rows=None)
    with pytest.raises(RuntimeError):
        _record(client)

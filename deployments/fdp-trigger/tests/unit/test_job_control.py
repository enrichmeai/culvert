"""Tests for the job_control writer.

The SQL itself now lives in the library adapter
(``data_pipeline_gcp_bigquery.BigQueryJobControlRepository``) -- spine AD-14,
no deployment writes ``job_control.*`` outside the port -- and is covered by
``data-pipeline-gcp-bigquery/tests/test_job_control.py``. What has to hold
*here* is that this deployment goes through that port, and that the two
guarantees it depends on survive the delegation. Neither is visible from the
return value, so both are asserted against the SQL and its parameters:

1. The row is written with DML, not the streaming insert API. A streamed row is
   invisible to the Dataflow job's terminal ``UPDATE`` until the streaming
   buffer flushes, which would leave the row ``running`` forever.
2. The status is Culvert's lowercase ``running`` (AD-17), and the columns are
   the authoritative ``pipeline_jobs`` shape the Java port reads.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_trigger.job_control import (
    JOB_TYPE,
    PIPELINE_NAME,
    STATUS_ON_COMPLETION,
    STATUS_ON_LAUNCH,
    SYSTEM_ID,
    record_trigger,
)

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


def test_writes_through_the_job_control_port():
    """AD-14: this module must not hand-roll its own job_control SQL."""
    import inspect

    import fdp_trigger.job_control as module

    source = inspect.getsource(module)
    for sql_keyword in ("INSERT INTO", "UPDATE ", "MERGE "):
        assert sql_keyword not in source, (
            f"job_control.py builds its own {sql_keyword} statement again"
        )
    assert module.BigQueryJobControlRepository.__module__.startswith(
        "data_pipeline_gcp_bigquery"
    )


def test_writes_lowercase_running_status():
    client = _mock_client()
    _record(client)
    assert _params(client)["status"] == "running"
    assert STATUS_ON_LAUNCH == "running"


def test_completion_status_is_the_lowercase_wire_value():
    """dedup.py imports this; the Dataflow job writes it (AD-17)."""
    assert STATUS_ON_COMPLETION == "succeeded"


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


def test_writes_this_deployments_identity():
    client = _mock_client()
    _record(client)
    params = _params(client)
    assert params["pipeline_name"] == PIPELINE_NAME
    assert params["system_id"] == SYSTEM_ID
    assert params["entity_type"] == "customer"
    assert params["job_type"] == JOB_TYPE.name


def test_binds_the_extract_date_as_a_date():
    client = _mock_client()
    _record(client)
    assert _params(client)["extract_date"] == date(2026, 4, 9)


def test_stamps_created_at_the_partition_column():
    client = _mock_client()
    _record(client)
    sql = client.query.call_args.args[0]
    assert "CURRENT_TIMESTAMP()" in sql


def test_marks_the_run_as_started():
    """The run is in flight from the moment the template is launched."""
    client = _mock_client()
    _record(client)
    assert _params(client)["started_at"] is not None


def test_raises_when_the_insert_affects_no_rows():
    """A write that moved nothing must fail loudly, never be assumed good."""
    client = _mock_client(affected_rows=0)
    with pytest.raises(RuntimeError, match="affected 0 rows"):
        _record(client)


def test_raises_when_the_affected_row_count_is_unavailable():
    client = _mock_client(affected_rows=None)
    with pytest.raises(RuntimeError):
        _record(client)

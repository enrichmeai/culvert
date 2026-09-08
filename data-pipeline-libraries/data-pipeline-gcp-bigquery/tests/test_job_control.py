"""Unit tests for the BigQuery ``JobControlRepository`` write path.

This adapter exists so that no deployment hand-rolls ``job_control`` SQL again
(spine AD-14). The properties the two former bypass writers depended on are
therefore asserted here, once, rather than in each deployment:

* DML query jobs, never ``insert_rows_json`` (a streamed row is invisible to
  the terminal ``UPDATE`` until the streaming buffer flushes);
* the authoritative 23-column ``pipeline_jobs`` shape;
* lowercase ``JobStatus`` wire values (AD-17);
* a statement that moved no row raises rather than passing quietly (AD-5).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from data_pipeline_core.job_control_api import (
    FailureStage,
    JobStatus,
    JobType,
    PipelineJob,
)

from data_pipeline_gcp_bigquery.job_control import (
    _INSERT_COLUMNS,
    BigQueryJobControlRepository,
    JobControlWriteError,
)

TABLE = "proj.job_control.pipeline_jobs"
RUN_ID = "auto_20260409_123456"


def _client(affected_rows=1):
    client = MagicMock()
    query_job = MagicMock()
    query_job.num_dml_affected_rows = affected_rows
    client.query.return_value = query_job
    return client


def _repo(client):
    return BigQueryJobControlRepository(client=client, table=TABLE)


def _job(**overrides):
    fields = dict(
        run_id=RUN_ID,
        system_id="GENERIC",
        pipeline_name="mainframe-segment-transform",
        extract_date=date(2026, 4, 9),
        status=JobStatus.RUNNING,
        job_type=JobType.TRANSFORMATION,
        entity_type="customer",
        source_file="fdp:ds.event_txn,fdp:ds.portfolio",
    )
    fields.update(overrides)
    return PipelineJob(**fields)


def _sql(client):
    return client.query.call_args.args[0]


def _params(client):
    job_config = client.query.call_args.kwargs["job_config"]
    return {p.name: p.value for p in job_config.query_parameters}


# ---------------------------------------------------------------------------
# Table resolution
# ---------------------------------------------------------------------------


def test_accepts_a_fully_qualified_table():
    assert _repo(_client()).table == TABLE


def test_qualifies_a_dataset_table_with_the_project():
    repo = BigQueryJobControlRepository(project_id="proj", client=_client())
    assert repo.table == TABLE


def test_rejects_a_bare_table_name():
    with pytest.raises(ValueError):
        BigQueryJobControlRepository(project_id="proj", client=_client(),
                                     table="pipeline_jobs")


def test_rejects_an_unqualified_table_with_no_project():
    with pytest.raises(ValueError):
        BigQueryJobControlRepository(client=_client(), table="job_control.pipeline_jobs")


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


def test_create_job_uses_dml_not_the_streaming_api():
    client = _client()
    _repo(client).create_job(_job())
    client.insert_rows_json.assert_not_called()
    client.query.assert_called_once()
    assert "INSERT INTO" in _sql(client)


def test_create_job_writes_the_authoritative_column_set():
    client = _client()
    _repo(client).create_job(_job())
    sql = _sql(client)
    for column in _INSERT_COLUMNS:
        assert column in sql, f"missing column {column}"
    # The predecessor-era REPEATED column is gone for good.
    assert "source_files" not in sql


def test_create_job_stamps_the_partition_column():
    """``created_at`` is the DAY partition field; it must never be NULL."""
    client = _client()
    _repo(client).create_job(_job())
    assert "CURRENT_TIMESTAMP()" in _sql(client)


def test_create_job_writes_the_callers_status_not_a_hardcoded_created():
    """fdp-trigger records a run as ``running`` at launch and reads it back."""
    client = _client()
    _repo(client).create_job(_job(status=JobStatus.RUNNING))
    assert _params(client)["status"] == "running"


def test_create_job_writes_lowercase_status_values():
    client = _client()
    _repo(client).create_job(_job(status=JobStatus.CREATED))
    assert _params(client)["status"] == "created"
    assert "RUNNING" not in _sql(client)
    assert "SUCCESS" not in _sql(client)


def test_create_job_writes_the_uppercase_job_type_the_ledger_holds():
    """Java writes ``jobType().name()``; both sides of the ledger are uppercase."""
    client = _client()
    _repo(client).create_job(_job())
    assert _params(client)["job_type"] == "TRANSFORMATION"


def test_create_job_carries_started_at_through():
    started = datetime(2026, 4, 9, 12, 34, 56, tzinfo=timezone.utc)
    client = _client()
    _repo(client).create_job(_job(started_at=started))
    assert _params(client)["started_at"] == started


def test_create_job_raises_when_no_row_was_written():
    client = _client(affected_rows=0)
    with pytest.raises(JobControlWriteError, match="affected 0 rows"):
        _repo(client).create_job(_job())


def test_create_job_raises_when_the_affected_row_count_is_unavailable():
    """BigQuery not reporting the count is not the same as it having worked."""
    client = _client(affected_rows=None)
    with pytest.raises(JobControlWriteError):
        _repo(client).create_job(_job())


def test_write_error_is_a_runtime_error():
    """Callers that caught the previous hand-rolled RuntimeError still catch it."""
    assert issubclass(JobControlWriteError, RuntimeError)


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


def test_update_status_stamps_started_at_when_running():
    client = _client()
    _repo(client).update_status(RUN_ID, JobStatus.RUNNING)
    sql = _sql(client)
    assert "started_at = CURRENT_TIMESTAMP()" in sql
    assert "completed_at" not in sql
    assert _params(client)["status"] == "running"


def test_update_status_stamps_completed_at_when_terminal():
    for status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
        client = _client()
        _repo(client).update_status(RUN_ID, status)
        assert "completed_at = CURRENT_TIMESTAMP()" in _sql(client)
        assert _params(client)["status"] == status.value


def test_update_status_records_the_total_when_given():
    client = _client()
    _repo(client).update_status(RUN_ID, JobStatus.SUCCEEDED, total_records=1234)
    assert "record_count = @record_count" in _sql(client)
    assert _params(client)["record_count"] == 1234


def test_update_status_omits_record_count_when_not_given():
    client = _client()
    _repo(client).update_status(RUN_ID, JobStatus.SUCCEEDED)
    assert "record_count" not in _sql(client)


def test_update_status_raises_when_no_row_matched():
    """A status transition that matched nothing leaves a run stuck (AD-5)."""
    client = _client(affected_rows=0)
    with pytest.raises(JobControlWriteError, match="affected 0 rows"):
        _repo(client).update_status(RUN_ID, JobStatus.SUCCEEDED)


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------


def test_mark_failed_writes_the_error_context():
    client = _client()
    _repo(client).mark_failed(
        RUN_ID, "CDC_STREAM_ERROR", "kafka went away",
        FailureStage.INGESTION, "gs://bucket/quarantine/run.json",
    )
    params = _params(client)
    assert params["status"] == "failed"
    assert params["error_code"] == "CDC_STREAM_ERROR"
    assert params["error_message"] == "kafka went away"
    assert params["failure_stage"] == "ingestion"
    assert params["error_file_path"] == "gs://bucket/quarantine/run.json"


def test_mark_failed_allows_an_absent_quarantine_uri():
    client = _client()
    _repo(client).mark_failed(
        RUN_ID, "E", "m", FailureStage.TRANSFORMATION,
    )
    assert _params(client)["error_file_path"] is None


def test_mark_failed_closes_the_run_out():
    client = _client()
    _repo(client).mark_failed(RUN_ID, "E", "m", FailureStage.LOAD)
    assert "completed_at = CURRENT_TIMESTAMP()" in _sql(client)


def test_mark_failed_raises_when_no_row_matched():
    client = _client(affected_rows=0)
    with pytest.raises(JobControlWriteError):
        _repo(client).mark_failed(RUN_ID, "E", "m", FailureStage.LOAD)


# ---------------------------------------------------------------------------
# Port conformance
# ---------------------------------------------------------------------------


def test_implements_the_write_path_of_the_port():
    """The three methods the Python writers call, per AD-14 rule 1."""
    from data_pipeline_core.contracts.job_control import JobControlRepository

    repo = _repo(_client())
    for method in ("create_job", "update_status", "mark_failed"):
        assert callable(getattr(repo, method))
        assert hasattr(JobControlRepository, method), (
            f"{method} is not on the port; a writer must not invent one"
        )


def test_is_discoverable_as_a_job_control_adapter():
    """AD-14 calls the deleted deployment-local class *unregistered*."""
    from data_pipeline_core.autoconfig import discover

    assert BigQueryJobControlRepository in discover().job_control

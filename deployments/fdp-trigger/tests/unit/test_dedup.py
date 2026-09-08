"""Tests for dedup check.

The status values in the filter are the load-bearing part of this module: the
previous version of these tests mocked the client and asserted only on the
return value, so the SQL could have named any status at all and every test
would still have passed. That is how a filter naming a status nothing ever
writes survived. These tests assert on the SQL text itself.
"""

from unittest.mock import MagicMock

from fdp_trigger.dedup import already_triggered
from fdp_trigger.job_control import (
    STATUSES_BLOCKING_RELAUNCH,
    STATUS_ON_COMPLETION,
    STATUS_ON_LAUNCH,
)

TABLE = "proj.job_control.pipeline_jobs"


def _mock_client(rows):
    client = MagicMock()
    query_job = MagicMock()
    query_job.result.return_value = iter(rows)
    client.query.return_value = query_job
    return client


def _executed_sql(client):
    """The SQL string handed to client.query (first positional argument)."""
    return client.query.call_args.args[0]


def test_no_existing_run_returns_false():
    """First launch for a date: nothing matches, so the launch proceeds."""
    client = _mock_client([])
    assert already_triggered(
        client=client,
        job_control_table=TABLE,
        extract_date="2026-04-09",
    ) is False


def test_existing_run_returns_true():
    """A matching row (running or succeeded) suppresses the relaunch."""
    client = _mock_client([MagicMock()])
    assert already_triggered(
        client=client,
        job_control_table=TABLE,
        extract_date="2026-04-09",
    ) is True


def test_query_uses_parameterised_pipeline_name():
    """Verify the dedup query is parameterised, not string-interpolated."""
    client = _mock_client([])
    already_triggered(
        client=client,
        job_control_table=TABLE,
        extract_date="2026-04-09",
    )
    call_args = client.query.call_args
    job_config = call_args.kwargs["job_config"]
    params = job_config.query_parameters
    param_names = {p.name for p in params}
    assert "pipeline_name" in param_names
    assert "extract_date" in param_names


def test_filter_uses_lowercase_culvert_status_values():
    """The filter names Culvert's lowercase JobStatus wire values (AD-17)."""
    client = _mock_client([])
    already_triggered(
        client=client, job_control_table=TABLE, extract_date="2026-04-09",
    )
    sql = _executed_sql(client)
    assert "'running'" in sql
    assert "'succeeded'" in sql
    assert "status IN ('running', 'succeeded')" in sql


def test_filter_does_not_use_the_dead_uppercase_vocabulary():
    """'RUNNING'/'SUCCESS' are not JobStatus members; nothing ever writes them."""
    client = _mock_client([])
    already_triggered(
        client=client, job_control_table=TABLE, extract_date="2026-04-09",
    )
    sql = _executed_sql(client)
    assert "RUNNING" not in sql
    assert "SUCCESS" not in sql


def test_failed_runs_do_not_block_a_relaunch():
    """
    A 'failed' row must not match the filter -- re-running a failed extract
    date is exactly the case this gate was latching closed.
    """
    client = _mock_client([])
    already_triggered(
        client=client, job_control_table=TABLE, extract_date="2026-04-09",
    )
    sql = _executed_sql(client)
    # Assert the PROPERTY, not the absence of a substring. 'failed' now appears
    # legitimately in the terminal-precedence CASE expression, so the old
    # `"failed" not in sql` check broke on a correct change - a substring proxy
    # standing in for the real invariant.
    assert "failed" not in STATUSES_BLOCKING_RELAUNCH
    blocking = sql.split("status IN (")[-1].split(")")[0]
    assert "failed" not in blocking, (
        f"a failed run must not block a relaunch; blocking set was: {blocking}"
    )


def test_blocking_statuses_match_the_writer_vocabulary():
    """The gate blocks on exactly what the two writers produce."""
    assert STATUSES_BLOCKING_RELAUNCH == (STATUS_ON_LAUNCH, STATUS_ON_COMPLETION)
    assert STATUS_ON_LAUNCH == "running"
    assert STATUS_ON_COMPLETION == "succeeded"

def test_dedup_reads_the_projection_not_raw_rows():
    """job_control is append-only, so one run leaves several rows.

    Matching raw rows would let a stale 'running' row from a since-failed run
    block every retry - the defect fixed in d89bf95, reintroduced by the
    append-only change. The dedup must therefore project per run_id with
    terminal precedence before testing status.
    """
    client = _mock_client([])
    already_triggered(client=client, job_control_table=TABLE, extract_date="2026-04-09")
    sql = _executed_sql(client)

    assert "ROW_NUMBER() OVER" in sql, "must project per run, not scan raw rows"
    assert "PARTITION BY run_id" in sql
    # Earliest terminal wins, so a terminal state cannot be flipped by a later row.
    assert "THEN 0 ELSE 1 END" in sql
    assert "rn = 1" in sql

"""Tests for dedup check."""

from unittest.mock import MagicMock

from fdp_trigger.dedup import already_triggered


def _mock_client(rows):
    client = MagicMock()
    query_job = MagicMock()
    query_job.result.return_value = iter(rows)
    client.query.return_value = query_job
    return client


def test_no_existing_run_returns_false():
    client = _mock_client([])
    assert already_triggered(
        client=client,
        job_control_table="proj.job_control.pipeline_jobs",
        extract_date="2026-04-09",
    ) is False


def test_existing_run_returns_true():
    client = _mock_client([MagicMock()])
    assert already_triggered(
        client=client,
        job_control_table="proj.job_control.pipeline_jobs",
        extract_date="2026-04-09",
    ) is True


def test_query_uses_parameterised_pipeline_name():
    """Verify the dedup query is parameterised, not string-interpolated."""
    client = _mock_client([])
    already_triggered(
        client=client,
        job_control_table="proj.job_control.pipeline_jobs",
        extract_date="2026-04-09",
    )
    call_args = client.query.call_args
    job_config = call_args.kwargs["job_config"]
    params = job_config.query_parameters
    param_names = {p.name for p in params}
    assert "pipeline_name" in param_names
    assert "extract_date" in param_names

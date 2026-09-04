"""Tests for the Flask trigger endpoint."""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "europe-west2")
    monkeypatch.setenv("FDP_PROJECT", "fdp-team-project")
    monkeypatch.setenv("FDP_DATASET", "fdp_dataset")
    monkeypatch.setenv("FDP_TABLES", "event_txn,portfolio,facility")
    monkeypatch.setenv("TEMPLATE_GCS_PATH", "gs://templates/spec.json")
    monkeypatch.setenv("OUTPUT_BUCKET", "output-bucket")
    monkeypatch.setenv("JOB_CONTROL_TABLE", "test-project.job_control.pipeline_jobs")
    monkeypatch.setenv("DATAFLOW_SERVICE_ACCOUNT", "df-sa@test-project.iam.gserviceaccount.com")
    monkeypatch.setenv("TEMP_LOCATION", "gs://temp/dataflow")


@pytest.fixture
def client(env_vars):
    from fdp_trigger.main import app
    app.config["TESTING"] = True
    return app.test_client()


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_invalid_date_returns_400(client):
    resp = client.post("/trigger", json={"extract_date": "not-a-date"})
    assert resp.status_code == 400
    assert "extract_date" in resp.get_json()["error"]


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
def test_not_ready_returns_204(mock_check, mock_bq, client):
    mock_check.return_value = MagicMock(
        is_ready=False, reason="Partition not found", partitions=[]
    )
    resp = client.post("/trigger", json={"extract_date": "2026-04-09"})
    assert resp.status_code == 204


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
@patch("fdp_trigger.main.already_triggered")
def test_already_triggered_returns_204(mock_dedup, mock_check, mock_bq, client):
    mock_check.return_value = MagicMock(is_ready=True, reason="OK", partitions=[])
    mock_dedup.return_value = True
    resp = client.post("/trigger", json={"extract_date": "2026-04-09"})
    assert resp.status_code == 204


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
@patch("fdp_trigger.main.already_triggered")
@patch("fdp_trigger.main.launch_segment_transform")
@patch("fdp_trigger.main.record_trigger")
def test_happy_path_launches_dataflow(
    mock_record, mock_launch, mock_dedup, mock_check, mock_bq, client
):
    mock_check.return_value = MagicMock(is_ready=True, reason="OK", partitions=[])
    mock_dedup.return_value = False
    mock_launch.return_value = "auto_20260409_123456"

    resp = client.post("/trigger", json={
        "extract_date": "2026-04-09",
        "segment": "customer",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "launched"
    assert body["run_id"] == "auto_20260409_123456"
    assert body["segment"] == "customer"
    assert body["extract_date"] == "2026-04-09"

    # Verify launch + record were called
    mock_launch.assert_called_once()
    mock_record.assert_called_once()


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
@patch("fdp_trigger.main.already_triggered")
@patch("fdp_trigger.main.launch_segment_transform")
@patch("fdp_trigger.main.record_trigger")
def test_launch_happens_before_the_job_control_row_is_written(
    mock_record, mock_launch, mock_dedup, mock_check, mock_bq, client
):
    """
    Deliberate ordering, pinned so a refactor cannot quietly invert it.

    Recording first would look safer, but a row written 'running' before a
    launch that then fails would latch the dedup gate permanently -- exactly
    the bug this flow was fixed for. Launching first is safe because the launch
    call only submits the job (workers take minutes to start) while the insert
    follows in milliseconds; and if the insert fails, the Dataflow job's
    terminal write finds no row and fails loudly.
    """
    mock_check.return_value = MagicMock(is_ready=True, reason="OK", partitions=[])
    mock_dedup.return_value = False
    mock_launch.return_value = "auto_20260409_123456"

    order = MagicMock()
    order.attach_mock(mock_launch, "launch")
    order.attach_mock(mock_record, "record")

    resp = client.post("/trigger", json={"extract_date": "2026-04-09"})
    assert resp.status_code == 200

    called = [name for name, _, _ in order.mock_calls]
    assert called == ["launch", "record"]


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
@patch("fdp_trigger.main.already_triggered")
@patch("fdp_trigger.main.launch_segment_transform")
@patch("fdp_trigger.main.record_trigger")
def test_the_job_is_told_which_job_control_table_to_complete(
    mock_record, mock_launch, mock_dedup, mock_check, mock_bq, client
):
    """
    The Dataflow job writes its terminal status to whichever table it is given.
    If that is not the table the dedup gate reads, the completion never reaches
    the gate and it stays latched -- so the trigger's own JOB_CONTROL_TABLE has
    to travel with the launch.
    """
    mock_check.return_value = MagicMock(is_ready=True, reason="OK", partitions=[])
    mock_dedup.return_value = False
    mock_launch.return_value = "auto_20260409_123456"

    client.post("/trigger", json={"extract_date": "2026-04-09"})

    launch_kwargs = mock_launch.call_args.kwargs
    dedup_table = mock_dedup.call_args.kwargs["job_control_table"]
    record_table = mock_record.call_args.kwargs["job_control_table"]
    assert launch_kwargs["job_control_table"] == "test-project.job_control.pipeline_jobs"
    assert launch_kwargs["job_control_table"] == dedup_table == record_table


@patch("fdp_trigger.main.bigquery.Client")
@patch("fdp_trigger.main.check_fdp_ready")
@patch("fdp_trigger.main.already_triggered")
@patch("fdp_trigger.main.launch_segment_transform")
@patch("fdp_trigger.main.record_trigger")
def test_default_segment_used_if_not_provided(
    mock_record, mock_launch, mock_dedup, mock_check, mock_bq, client
):
    mock_check.return_value = MagicMock(is_ready=True, reason="OK", partitions=[])
    mock_dedup.return_value = False
    mock_launch.return_value = "auto_20260409_123456"

    resp = client.post("/trigger", json={"extract_date": "2026-04-09"})
    assert resp.status_code == 200
    assert resp.get_json()["segment"] == "customer"  # DEFAULT_SEGMENT

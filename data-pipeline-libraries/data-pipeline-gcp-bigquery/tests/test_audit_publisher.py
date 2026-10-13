"""Tests for BigQueryAuditEventPublisher (#257) - no real BigQuery client.

Java sibling: ``BigQueryAuditEventPublisher`` and its ``BigQueryAuditEventPublisherContractTest``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import BadRequest

from data_pipeline_contract_tests import AuditEventPublisherContract
from data_pipeline_core.audit.events import CONTRACT_VERSION, AuditEvent, EventKind
from data_pipeline_core.contracts.audit import AuditEventPublisher
from data_pipeline_gcp_bigquery import BigQueryAuditEventPublisher


def _client(fail: bool = False) -> MagicMock:
    client = MagicMock()
    job = MagicMock()
    if fail:
        job.result.side_effect = BadRequest("Table job_control.audit_events was not found")
    client.query.return_value = job
    return client


def _event(kind=EventKind.RUN_END, **overrides) -> AuditEvent:
    fields = dict(
        run_id="20260908T091400Z-7f3a",
        system_id="Generic",
        entity="customers",
        event_kind=kind,
        event_ts=datetime(2026, 9, 8, 9, 14, tzinfo=timezone.utc),
        payload={"record_count": 42},
    )
    fields.update(overrides)
    return AuditEvent(**fields)


def _params(client) -> dict:
    job_config = client.query.call_args.kwargs["job_config"]
    return {p.name: (p.type_, p.value) for p in job_config.query_parameters}


class TestBigQueryAuditEventPublisherContract(AuditEventPublisherContract):
    @pytest.fixture
    def client(self):
        return _client()

    @pytest.fixture
    def publisher(self, client):
        return BigQueryAuditEventPublisher(client, "proj")

    @pytest.fixture
    def failing_publisher(self):
        return BigQueryAuditEventPublisher(_client(fail=True), "proj")

    @pytest.fixture
    def delivered(self, client):
        # A write is acknowledged once its job has been waited on.
        return lambda: client.query.return_value.result.call_count


def test_it_is_an_audit_event_publisher():
    assert isinstance(BigQueryAuditEventPublisher(_client(), "proj"), AuditEventPublisher)


def test_writes_the_section_4_columns_to_job_control_audit_events_by_default():
    client = _client()
    BigQueryAuditEventPublisher(client, "proj").publish(_event())

    sql = client.query.call_args.args[0]
    assert sql.startswith("INSERT INTO `proj.job_control.audit_events` (")
    assert ("run_id, system_id, entity, event_kind, event_ts, extract_date, "
            "payload, producer, contract_version, environment") in sql
    assert "PARSE_JSON(@payload)" in sql
    client.query.return_value.result.assert_called_once()


def test_the_dataset_and_table_can_be_named():
    client = _client()
    BigQueryAuditEventPublisher(client, "proj", dataset="audit_ds", table="events").publish(_event())

    assert "`proj.audit_ds.events`" in client.query.call_args.args[0]


def test_every_value_is_a_typed_query_parameter():
    client = _client()
    event = _event(
        extract_date=date(2026, 9, 8), producer="odp-loader", environment="dev",
        payload={"record_count": 42, "note": 'say "hi"'},
    )
    BigQueryAuditEventPublisher(client, "proj").publish(event)

    params = _params(client)
    assert params["run_id"] == ("STRING", "20260908T091400Z-7f3a")
    assert params["system_id"] == ("STRING", "Generic")
    assert params["entity"] == ("STRING", "customers")
    assert params["event_kind"] == ("STRING", "RUN_END")
    assert params["event_ts"] == ("TIMESTAMP", datetime(2026, 9, 8, 9, 14, tzinfo=timezone.utc))
    assert params["extract_date"] == ("DATE", date(2026, 9, 8))
    assert params["producer"] == ("STRING", "odp-loader")
    assert params["environment"] == ("STRING", "dev")
    assert params["contract_version"] == ("STRING", CONTRACT_VERSION)
    assert params["payload"][0] == "STRING"
    assert json.loads(params["payload"][1]) == {"record_count": 42, "note": 'say "hi"'}
    assert "say" not in client.query.call_args.args[0]  # values never reach the SQL text


def test_optional_columns_are_null_when_absent():
    client = _client()
    BigQueryAuditEventPublisher(client, "proj").publish(_event())

    params = _params(client)
    assert params["extract_date"] == ("DATE", None)
    assert params["producer"] == ("STRING", None)
    assert params["environment"] == ("STRING", None)


def test_a_payload_value_json_cannot_carry_is_written_as_text():
    client = _client()
    when = datetime(2026, 9, 8, tzinfo=timezone.utc)
    BigQueryAuditEventPublisher(client, "proj").publish(
        _event(payload={"record_count": 1, "at": when}))

    assert json.loads(_params(client)["payload"][1])["at"] == str(when)


def test_a_failed_run_level_write_raises_naming_the_event_and_counts_it():
    publisher = BigQueryAuditEventPublisher(_client(fail=True), "proj")

    with pytest.raises(RuntimeError, match="RUN_END.*20260908T091400Z-7f3a") as raised:
        publisher.publish(_event())

    assert isinstance(raised.value.__cause__, BadRequest)
    assert publisher.audit_failure_count == 1


def test_a_failed_aggregate_write_is_logged_at_error_and_counted(caplog):
    publisher = BigQueryAuditEventPublisher(_client(fail=True), "proj")
    event = _event(EventKind.RECORD_VALIDATED, payload={"count": 7})

    with caplog.at_level(logging.ERROR):
        publisher.publish(event)

    assert publisher.audit_failure_count == 1
    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert "RECORD_VALIDATED" in record.getMessage() and "'count': 7" in record.getMessage()


def test_a_payload_json_cannot_encode_fails_a_run_level_event_and_is_counted():
    # NaN is not JSON (PARSE_JSON would refuse it); the failure takes the same road as a failed write.
    client = _client()
    publisher = BigQueryAuditEventPublisher(client, "proj")

    with pytest.raises(RuntimeError, match="RUN_END") as raised:
        publisher.publish(_event(payload={"record_count": float("nan")}))

    assert isinstance(raised.value.__cause__, ValueError)
    assert publisher.audit_failure_count == 1
    client.query.assert_not_called()


def test_a_payload_json_cannot_encode_on_an_aggregate_is_logged_not_raised(caplog):
    circular: dict = {}
    circular["self"] = circular
    publisher = BigQueryAuditEventPublisher(_client(), "proj")

    with caplog.at_level(logging.ERROR):
        publisher.publish(_event(EventKind.RECORD_VALIDATED, payload={"count": 1, "loop": circular}))

    assert publisher.audit_failure_count == 1
    assert "RECORD_VALIDATED" in caplog.records[-1].getMessage()


def test_flush_is_a_no_op():
    client = _client()
    BigQueryAuditEventPublisher(client, "proj").flush()

    client.query.assert_not_called()


@pytest.mark.parametrize("has_client, project", [(False, "proj"), (True, None)])
def test_rejects_a_missing_client_or_project(has_client, project):
    with pytest.raises(TypeError):
        BigQueryAuditEventPublisher(_client() if has_client else None, project)


@pytest.mark.parametrize("name", ["dataset", "table"])
def test_rejects_a_missing_dataset_or_table(name):
    with pytest.raises(TypeError):
        BigQueryAuditEventPublisher(_client(), "proj", **{name: None})


def test_publish_rejects_none():
    with pytest.raises(TypeError):
        BigQueryAuditEventPublisher(_client(), "proj").publish(None)

"""BigQueryTableSink: batch load jobs into a table (#13), against a recording client."""

from __future__ import annotations

import datetime
import decimal

import pytest
from google.cloud import bigquery

import data_pipeline_gcp_bigquery.table_sink as table_sink_module
from data_pipeline_gcp_bigquery import BigQueryTableSink


class Job:
    def __init__(self, error=None):
        self.error = error
        self.waited = False

    def result(self):
        self.waited = True
        if self.error:
            raise self.error


class Client:
    def __init__(self, fail_on=None):
        self.loads = []
        self.fail_on = fail_on

    def load_table_from_json(self, rows, destination, job_config=None):
        job = Job(RuntimeError("load failed") if len(self.loads) == self.fail_on else None)
        self.loads.append((rows, destination, job_config, job))
        return job


def rows(n):
    return ({"id": i} for i in range(n))


def test_records_load_in_batches_each_waited_on():
    client = Client()
    BigQueryTableSink("p.d.t", client=client, batch_size=2).write(rows(5), None)

    assert [r for r, *_ in client.loads] == [[{"id": 0}, {"id": 1}], [{"id": 2}, {"id": 3}],
                                             [{"id": 4}]]
    assert all(dest == "p.d.t" for _, dest, _, _ in client.loads)
    assert all(isinstance(cfg, bigquery.LoadJobConfig) for _, _, cfg, _ in client.loads)
    assert all(job.waited for *_, job in client.loads)


def test_a_truncating_write_truncates_once_then_appends():
    client = Client()
    BigQueryTableSink("d.t", client=client, write_disposition="WRITE_TRUNCATE",
                      batch_size=2).write(rows(3), None)
    assert [cfg.write_disposition for _, _, cfg, _ in client.loads] == [
        "WRITE_TRUNCATE", "WRITE_APPEND"]


def test_a_failed_load_raises_and_nothing_after_it_is_loaded():
    client = Client(fail_on=1)
    with pytest.raises(RuntimeError, match="load failed"):
        BigQueryTableSink("p.d.t", client=client, batch_size=2).write(rows(6), None)
    assert len(client.loads) == 2


def test_no_records_no_load_job():
    client = Client()
    BigQueryTableSink("p.d.t", client=client).write(iter([]), None)
    assert client.loads == []


def test_dates_and_decimals_are_sent_as_strings_and_the_schema_is_passed():
    client = Client()
    schema = [bigquery.SchemaField("at", "TIMESTAMP")]
    record = {"at": datetime.datetime(2026, 10, 9, 7, 0, tzinfo=datetime.timezone.utc),
              "day": datetime.date(2026, 10, 9), "amount": decimal.Decimal("12.50"),
              "tags": [{"since": datetime.date(2026, 1, 1)}]}
    BigQueryTableSink("p.d.t", client=client, schema=schema).write([record], None)
    (sent, _, config, _), = client.loads
    assert sent == [{"at": "2026-10-09T07:00:00+00:00", "day": "2026-10-09",
                     "amount": "12.50", "tags": [{"since": "2026-01-01"}]}]
    assert [f.name for f in config.schema] == ["at"]


def test_without_a_client_one_is_made_for_the_tables_project_on_first_write(monkeypatch):
    made = []

    def fake_client(project=None):
        made.append(project)
        return Client()

    monkeypatch.setattr(bigquery, "Client", fake_client)
    sink = BigQueryTableSink("proj-1.d.t")
    assert made == [], "no client until something is written"
    sink.write(rows(1), None)
    sink.write(rows(1), None)
    assert made == ["proj-1"]


def test_a_domain_scoped_project_is_accepted():
    sink = BigQueryTableSink("example.com:proj.d.t", client=Client())
    assert sink._project == "example.com:proj"
    assert BigQueryTableSink("d.t", client=Client())._project is None


def test_bad_arguments_are_refused():
    for bad in ("", "t", "a.b.c.d", "p.d.t bad"):
        with pytest.raises(ValueError, match="project.dataset.table"):
            BigQueryTableSink(bad)
    with pytest.raises(ValueError, match="write_disposition"):
        BigQueryTableSink("d.t", write_disposition="WRITE_SOMETIMES")
    with pytest.raises(ValueError, match="batch_size"):
        BigQueryTableSink("d.t", batch_size=0)
    with pytest.raises(TypeError, match="mapping records"):
        BigQueryTableSink("d.t", client=Client()).write([("a",)], None)


def test_it_is_a_sink():
    from data_pipeline_core import Sink
    assert isinstance(BigQueryTableSink("d.t"), Sink)
    assert table_sink_module.__all__ == ["BigQueryTableSink"]


@pytest.mark.parametrize("value, field", [
    (float("nan"), "x"), (float("inf"), "x"), (decimal.Decimal("NaN"), "x"),
    (b"raw", "x"), ({1, 2}, "x"), ({"inner": object()}, "x.inner"), ([float("-inf")], "x"),
])
def test_a_value_json_cannot_carry_is_refused_before_its_batch_is_sent(value, field):
    client = Client()
    with pytest.raises(ValueError, match=f"field '{field}'"):
        BigQueryTableSink("p.d.t", client=client).write([{"ok": 1}, {"x": value}], None)
    assert client.loads == []


def test_an_empty_truncating_write_sends_nothing():
    client = Client()
    BigQueryTableSink("p.d.t", client=client, write_disposition="WRITE_TRUNCATE").write([], None)
    assert client.loads == []

"""Mockito-style unit tests for BigQueryWarehouse — no real GCP."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_gcp_bigquery import BigQueryWarehouse


@pytest.fixture
def mock_client():
    return MagicMock()


def test_constructor_rejects_none_project():
    with pytest.raises(TypeError):
        BigQueryWarehouse(None, MagicMock())


def test_constructor_rejects_none_client():
    with pytest.raises(TypeError):
        BigQueryWarehouse("my-project", None)


def test_query_streams_rows_as_dicts(mock_client):
    row1 = MagicMock()
    row1.items.return_value = [("id", 1), ("name", "alice")]
    row2 = MagicMock()
    row2.items.return_value = [("id", 2), ("name", "bob")]
    job = MagicMock()
    job.result.return_value = [row1, row2]
    mock_client.query.return_value = job

    w = BigQueryWarehouse("my-project", mock_client)
    rows = list(w.query("SELECT id, name FROM ds.t"))

    assert rows == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
    mock_client.query.assert_called_once_with("SELECT id, name FROM ds.t")


def test_execute_discards_result(mock_client):
    job = MagicMock()
    mock_client.query.return_value = job

    w = BigQueryWarehouse("my-project", mock_client)
    w.execute("UPDATE ds.t SET x = 1 WHERE id = 1")

    job.result.assert_called_once()


def test_load_from_uri_returns_output_rows(mock_client):
    load_job = MagicMock()
    load_job.output_rows = 1234
    mock_client.load_table_from_uri.return_value = load_job

    w = BigQueryWarehouse("my-project", mock_client)
    n = w.load_from_uri("gs://bucket/file.csv", "ds.t", schema=MagicMock())

    assert n == 1234
    load_job.result.assert_called_once()


def test_merge_is_unimplemented(mock_client):
    w = BigQueryWarehouse("my-project", mock_client)
    with pytest.raises(NotImplementedError):
        w.merge("src", "tgt", ["id"])


def test_copy_returns_target_row_count(mock_client):
    job = MagicMock()
    mock_client.copy_table.return_value = job
    table = MagicMock()
    table.num_rows = 5000
    mock_client.get_table.return_value = table

    w = BigQueryWarehouse("my-project", mock_client)
    n = w.copy("ds.src", "ds.tgt")

    assert n == 5000
    job.result.assert_called_once()


def test_table_exists_true(mock_client):
    mock_client.get_table.return_value = MagicMock()
    w = BigQueryWarehouse("my-project", mock_client)
    assert w.table_exists("ds.t") is True


def test_table_exists_false_on_exception(mock_client):
    mock_client.get_table.side_effect = Exception("not found")
    w = BigQueryWarehouse("my-project", mock_client)
    assert w.table_exists("ds.missing") is False


def test_query_null_sql_raises(mock_client):
    w = BigQueryWarehouse("my-project", mock_client)
    with pytest.raises(TypeError):
        list(w.query(None))

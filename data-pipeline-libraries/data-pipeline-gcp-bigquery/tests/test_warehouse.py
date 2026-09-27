"""Mockito-style unit tests for BigQueryWarehouse — no real GCP."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_pipeline_contract_tests import WarehouseContract
from data_pipeline_core.contracts.warehouse import LoadOptions
from data_pipeline_gcp_bigquery import BigQueryWarehouse
from data_pipeline_gcp_bigquery.warehouse import merge_sql


@pytest.fixture
def mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# Contract tests — bind WarehouseContract to BigQueryWarehouse
# ---------------------------------------------------------------------------

class TestBigQueryWarehouseContract(WarehouseContract):
    """Exercise every WarehouseContract guarantee against a mocked BQ client.

    The mixin requires one fixture:
      ``warehouse`` — a BigQueryWarehouse configured so that:
        * ``query("SELECT id FROM contract_test_table")`` yields ``{"id": 1}``
        * ``table_exists("contract_test_table")`` is True
        * ``table_exists("contract_missing_table")`` is False
    """

    @pytest.fixture
    def warehouse(self):
        client = MagicMock()

        # query() result: one row with {"id": 1}
        row = MagicMock()
        row.items.return_value = [("id", 1)]
        job = MagicMock()
        job.result.return_value = [row]
        client.query.return_value = job

        # table_exists: returns True for the known table, False for missing
        def _get_table(fqtn):
            if fqtn == "contract_test_table":
                # merge reads the target's schema for its column list
                return _table("id", "name")
            raise Exception(f"Not found: {fqtn}")

        client.get_table.side_effect = _get_table
        # the MERGE job reports 2 affected rows
        job.num_dml_affected_rows = 2

        return BigQueryWarehouse("test-project", client)


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
    n = w.load_from_uri(
        "gs://bucket/file.csv", "ds.t", schema=MagicMock(),
        options=LoadOptions.append(),
    )

    assert n == 1234
    load_job.result.assert_called_once()


def test_load_from_uri_sets_the_requested_write_disposition(mock_client):
    """The disposition must reach the job config.

    Without it BigQuery applies its own default of WRITE_APPEND, which is
    how re-running an extract silently doubled the data.
    """
    load_job = MagicMock()
    load_job.output_rows = 2
    mock_client.load_table_from_uri.return_value = load_job
    job_config = MagicMock()

    w = BigQueryWarehouse("my-project", mock_client)
    w.load_from_uri(
        "gs://bucket/file.csv", "ds.t", schema=job_config,
        options=LoadOptions.truncate(),
    )

    assert job_config.write_disposition == "WRITE_TRUNCATE"


def test_load_from_uri_appends_a_partition_decorator_when_scoped(mock_client):
    """A partition-scoped load targets `table$YYYYMMDD`, not the bare table."""
    load_job = MagicMock()
    load_job.output_rows = 1
    mock_client.load_table_from_uri.return_value = load_job

    w = BigQueryWarehouse("my-project", mock_client)
    w.load_from_uri(
        "gs://bucket/file.csv", "ds.t", schema=MagicMock(),
        options=LoadOptions.truncate_partition("20260601"),
    )

    destination = mock_client.load_table_from_uri.call_args[0][1]
    assert destination == "ds.t$20260601"


def test_load_from_uri_requires_options(mock_client):
    """No defaulted disposition: choosing one must be a visible act."""
    w = BigQueryWarehouse("my-project", mock_client)
    with pytest.raises(TypeError):
        w.load_from_uri("gs://bucket/file.csv", "ds.t", schema=MagicMock())


def _table(*columns):
    table = MagicMock()
    fields = []
    for name in columns:
        field = MagicMock()
        field.name = name
        fields.append(field)
    table.schema = fields
    return table


def _stub_merge(client, columns, affected):
    client.get_table.return_value = _table(*columns)
    job = MagicMock()
    job.num_dml_affected_rows = affected
    client.query.return_value = job
    return job


def test_merge_updates_non_key_columns_and_inserts_all_from_the_target_schema(mock_client):
    job = _stub_merge(mock_client, ["id", "region", "name", "amount"], 7)
    w = BigQueryWarehouse("my-project", mock_client)

    assert w.merge("ds.staging", "my-project.ds.fact", ["ID", "region"]) == 7

    mock_client.get_table.assert_called_once_with("my-project.ds.fact")
    job.result.assert_called_once()
    # Keys match case-insensitively and are written in the target's spelling.
    assert mock_client.query.call_args.args[0] == (
        "MERGE `my-project.ds.fact` T\n"
        "USING `ds.staging` S\n"
        "ON T.`id` = S.`id` AND T.`region` = S.`region`\n"
        "WHEN MATCHED THEN UPDATE SET `name` = S.`name`, `amount` = S.`amount`\n"
        "WHEN NOT MATCHED THEN INSERT (`id`, `region`, `name`, `amount`) "
        "VALUES (S.`id`, S.`region`, S.`name`, S.`amount`)"
    )


def test_merge_on_a_key_only_table_only_inserts(mock_client):
    # Nothing to update: GoogleSQL's UPDATE SET needs at least one item.
    _stub_merge(mock_client, ["id"], 3)
    w = BigQueryWarehouse("my-project", mock_client)

    assert w.merge("ds.new_keys", "ds.keys", ["id"]) == 3

    sql = mock_client.query.call_args.args[0]
    assert "WHEN MATCHED" not in sql
    assert sql.endswith("WHEN NOT MATCHED THEN INSERT (`id`) VALUES (S.`id`)")


def test_merge_rejects_a_key_missing_from_the_target_naming_it_before_running_anything(mock_client):
    _stub_merge(mock_client, ["id"], 0)
    w = BigQueryWarehouse("my-project", mock_client)

    with pytest.raises(ValueError, match="customer_id") as err:
        w.merge("ds.staging", "ds.fact", ["customer_id"])

    assert "ds.fact" in str(err.value)
    mock_client.query.assert_not_called()


def test_merge_joins_once_on_a_key_named_twice(mock_client):
    _stub_merge(mock_client, ["id", "name"], 1)
    w = BigQueryWarehouse("my-project", mock_client)

    w.merge("ds.staging", "ds.fact", ["id", "ID"])

    assert "ON T.`id` = S.`id`\nWHEN MATCHED" in mock_client.query.call_args.args[0]


def test_merge_reports_zero_when_bigquery_gives_no_dml_count(mock_client):
    _stub_merge(mock_client, ["id"], None)
    w = BigQueryWarehouse("my-project", mock_client)

    assert w.merge("ds.staging", "ds.fact", ["id"]) == 0


def test_merge_escapes_backticks_in_identifiers():
    sql = merge_sql("p.d.s", "p.d.t", ["id", "we`ird"], ["id"])
    assert "UPDATE SET `we\\`ird` = S.`we\\`ird`" in sql


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

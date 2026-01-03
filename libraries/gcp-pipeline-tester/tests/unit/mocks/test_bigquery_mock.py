"""Unit tests for mocks/bigquery_mock.py - BigQuery mock classes."""

import unittest

from gcp_pipeline_tester.mocks.bigquery_mock import BigQueryClientMock, BigQueryTableMock


class TestBigQueryClientMock(unittest.TestCase):
    """Tests for BigQueryClientMock class."""

    def test_init(self):
        """Test BigQueryClientMock initialization."""
        mock = BigQueryClientMock()

        self.assertEqual(mock.inserted_rows, [])
        self.assertEqual(mock.tables, {})

    def test_insert_rows_json(self):
        """Test insert_rows_json stores rows."""
        mock = BigQueryClientMock()
        rows = [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]

        errors = mock.insert_rows_json("project.dataset.table", rows)

        self.assertEqual(errors, [])
        self.assertEqual(len(mock.inserted_rows), 2)
        self.assertEqual(mock.inserted_rows[0]["name"], "John")

    def test_insert_rows_json_creates_table(self):
        """Test insert_rows_json creates table entry."""
        mock = BigQueryClientMock()

        mock.insert_rows_json("project.dataset.users", [{"id": "1"}])

        self.assertIn("project.dataset.users", mock.tables)
        self.assertEqual(len(mock.tables["project.dataset.users"]), 1)

    def test_insert_rows_multiple_tables(self):
        """Test inserting to multiple tables."""
        mock = BigQueryClientMock()

        mock.insert_rows_json("dataset.users", [{"id": "1"}])
        mock.insert_rows_json("dataset.orders", [{"order_id": "100"}])

        self.assertEqual(len(mock.tables["dataset.users"]), 1)
        self.assertEqual(len(mock.tables["dataset.orders"]), 1)

    def test_get_table(self):
        """Test get_table returns mock with table_id."""
        mock = BigQueryClientMock()

        table = mock.get_table("project.dataset.table")

        self.assertEqual(table.table_id, "project.dataset.table")

    def test_create_table(self):
        """Test create_table initializes empty table."""
        mock = BigQueryClientMock()

        mock.create_table("project.dataset.new_table", [])

        self.assertIn("project.dataset.new_table", mock.tables)
        self.assertEqual(mock.tables["project.dataset.new_table"], [])

    def test_query_returns_mock(self):
        """Test query returns mock result."""
        mock = BigQueryClientMock()

        result = mock.query("SELECT * FROM table")

        self.assertIsNotNone(result)
        self.assertEqual(result.result(), [])

    def test_get_inserted_rows_all(self):
        """Test get_inserted_rows returns all rows."""
        mock = BigQueryClientMock()
        mock.insert_rows_json("table1", [{"id": "1"}])
        mock.insert_rows_json("table2", [{"id": "2"}])

        rows = mock.get_inserted_rows()

        self.assertEqual(len(rows), 2)

    def test_get_inserted_rows_by_table(self):
        """Test get_inserted_rows for specific table."""
        mock = BigQueryClientMock()
        mock.insert_rows_json("table1", [{"id": "1"}])
        mock.insert_rows_json("table2", [{"id": "2"}, {"id": "3"}])

        rows = mock.get_inserted_rows("table2")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], "2")

    def test_get_inserted_rows_missing_table(self):
        """Test get_inserted_rows for missing table returns empty."""
        mock = BigQueryClientMock()

        rows = mock.get_inserted_rows("nonexistent")

        self.assertEqual(rows, [])

    def test_reset(self):
        """Test reset clears all state."""
        mock = BigQueryClientMock()
        mock.insert_rows_json("table", [{"id": "1"}])

        mock.reset()

        self.assertEqual(mock.inserted_rows, [])
        self.assertEqual(mock.tables, {})


class TestBigQueryTableMock(unittest.TestCase):
    """Tests for BigQueryTableMock class."""

    def test_init(self):
        """Test BigQueryTableMock initialization."""
        table = BigQueryTableMock("project.dataset.table")

        self.assertEqual(table.table_id, "project.dataset.table")
        self.assertEqual(table.rows, [])

    def test_insert_rows(self):
        """Test insert_rows stores rows."""
        table = BigQueryTableMock("project.dataset.table")

        errors = table.insert_rows([{"id": "1"}, {"id": "2"}])

        self.assertEqual(errors, [])
        self.assertEqual(len(table.rows), 2)

    def test_get_rows(self):
        """Test get_rows returns all rows."""
        table = BigQueryTableMock("project.dataset.table")
        table.insert_rows([{"id": "1"}, {"id": "2"}])

        rows = table.get_rows()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], "1")

    def test_get_rows_returns_copy(self):
        """Test get_rows returns copy of rows."""
        table = BigQueryTableMock("project.dataset.table")
        table.insert_rows([{"id": "1"}])

        rows = table.get_rows()
        rows.append({"id": "2"})

        # Original should be unchanged
        self.assertEqual(len(table.rows), 1)


if __name__ == "__main__":
    unittest.main()


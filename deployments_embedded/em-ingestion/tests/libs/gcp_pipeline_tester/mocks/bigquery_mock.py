"""
BigQuery Mock Module

Mock objects for BigQuery testing.
"""

from typing import Dict, List, Any
from unittest.mock import Mock


class BigQueryClientMock:
    """
    Mock BigQuery client for testing.

    Provides a mock interface for BigQuery operations without
    requiring actual BigQuery connectivity.

    Example:
        >>> mock_client = BigQueryClientMock()
        >>> errors = mock_client.insert_rows_json('project.dataset.table', [{'id': '1'}])
        >>> assert errors == []
    """

    def __init__(self):
        """Initialize mock BigQuery client."""
        self.inserted_rows: List[Dict[str, Any]] = []
        self.tables: Dict[str, List[Dict]] = {}

    def insert_rows_json(self, table_id: str, rows: List[Dict]) -> List:
        """
        Mock insert rows operation.

        Args:
            table_id: BigQuery table ID
            rows: List of rows to insert

        Returns:
            List of errors (empty if successful)
        """
        self.inserted_rows.extend(rows)
        if table_id not in self.tables:
            self.tables[table_id] = []
        self.tables[table_id].extend(rows)
        return []

    def get_table(self, table_id: str):
        """Mock get table operation."""
        return Mock(table_id=table_id)

    def create_table(self, table_id: str, schema: List) -> None:
        """Mock create table operation."""
        self.tables[table_id] = []

    def query(self, query: str) -> Any:
        """Mock query operation."""
        return Mock(result=lambda: [])

    def get_inserted_rows(self, table_id: str = None) -> List:
        """Get rows inserted during test."""
        if table_id:
            return self.tables.get(table_id, [])
        return self.inserted_rows.copy()

    def reset(self) -> None:
        """Reset mock state."""
        self.inserted_rows = []
        self.tables = {}


class BigQueryTableMock:
    """
    Mock BigQuery table for testing.

    Simulates table operations without actual BigQuery connectivity.

    Example:
        >>> table = BigQueryTableMock('project.dataset.table')
        >>> table.insert_rows([{'id': '1', 'name': 'John'}])
    """

    def __init__(self, table_id: str):
        """
        Initialize mock table.

        Args:
            table_id: Full BigQuery table ID
        """
        self.table_id = table_id
        self.rows: List[Dict[str, Any]] = []

    def insert_rows(self, rows: List[Dict]) -> List:
        """Mock insert rows."""
        self.rows.extend(rows)
        return []

    def get_rows(self) -> List[Dict]:
        """Get all inserted rows."""
        return self.rows.copy()


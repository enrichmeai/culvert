"""Warehouse contract test mixin."""

from __future__ import annotations

import pytest


class WarehouseContract:
    """Mixin — subclasses provide ``warehouse`` fixture configured so that
    ``query("SELECT id FROM contract_test_table")`` yields ``{"id": 1}``,
    ``table_exists("contract_test_table")`` is True, and
    ``table_exists("contract_missing_table")`` is False.
    """

    def test_query_streams_rows(self, warehouse):
        rows = list(warehouse.query("SELECT id FROM contract_test_table"))
        assert len(rows) >= 1
        assert "id" in rows[0]

    def test_table_exists_known_true(self, warehouse):
        assert warehouse.table_exists("contract_test_table") is True

    def test_table_exists_missing_false(self, warehouse):
        assert warehouse.table_exists("contract_missing_table") is False

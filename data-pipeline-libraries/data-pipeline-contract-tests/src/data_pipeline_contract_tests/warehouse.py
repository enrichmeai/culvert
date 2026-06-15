"""Warehouse contract test mixin.

Java mirror: ``com.enrichmeai.culvert.contracttests.WarehouseContractTest``
"""

from __future__ import annotations

import pytest


class WarehouseContract:
    """Mixin — subclasses provide ``warehouse`` fixture configured so that
    ``query("SELECT id FROM contract_test_table")`` yields ``{"id": 1}``,
    ``table_exists("contract_test_table")`` is True, and
    ``table_exists("contract_missing_table")`` is False.

    Java mirror: ``WarehouseContractTest`` (Sprint-5 deliverable; T15.4
    added ``known_table``/``missing_table`` hook — Python subclasses
    override the fixture to supply qualified names if needed).
    """

    def test_query_streams_rows(self, warehouse):
        rows = list(warehouse.query("SELECT id FROM contract_test_table"))
        assert len(rows) >= 1
        assert "id" in rows[0]

    def test_table_exists_known_true(self, warehouse):
        assert warehouse.table_exists("contract_test_table") is True

    def test_table_exists_missing_false(self, warehouse):
        assert warehouse.table_exists("contract_missing_table") is False

    def test_null_sql_rejected(self, warehouse):
        # Java: ``nullSqlRejected`` — query(null, ...) must raise.
        with pytest.raises((TypeError, ValueError)):
            warehouse.query(None)

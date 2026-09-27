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

    Merge: ``contract_test_table`` has an ``id`` column and no column named
    ``contract_no_such_column``, and ``merge_source_table`` can be merged
    into it on ``id``. A backend that cannot express an upsert sets
    ``merge_supported = False``, which is a promise that ``merge`` raises
    ``NotImplementedError`` naming it, rather than appending, or returning 0
    as if nothing matched.

    Java mirror: ``WarehouseContractTest`` (Sprint-5 deliverable; T15.4
    added ``known_table``/``missing_table`` hook — Python subclasses
    override the fixture to supply qualified names if needed).
    """

    merge_supported = True
    merge_source_table = "contract_merge_source"

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

    def test_merge_upserts_on_keys_and_reports_rows_affected(self, warehouse):
        # Java: ``mergeUpsertsOnKeysAndReportsRowsAffected``.
        if not self.merge_supported:
            pytest.skip("backend declares merge unsupported")
        affected = warehouse.merge(
            self.merge_source_table, "contract_test_table", ["id"]
        )
        assert isinstance(affected, int)
        assert affected >= 0

    def test_merge_rejects_a_key_the_target_does_not_have_naming_it(self, warehouse):
        # Java: ``mergeRejectsAKeyTheTargetDoesNotHaveNamingIt``.
        if not self.merge_supported:
            pytest.skip("backend declares merge unsupported")
        with pytest.raises(ValueError, match="contract_no_such_column"):
            warehouse.merge(
                self.merge_source_table,
                "contract_test_table",
                ["id", "contract_no_such_column"],
            )

    def test_merge_rejects_empty_or_none_keys(self, warehouse):
        # Java: ``mergeRejectsEmptyOrNullKeys``.
        if not self.merge_supported:
            pytest.skip("backend declares merge unsupported")
        with pytest.raises(ValueError):
            warehouse.merge(self.merge_source_table, "contract_test_table", [])
        with pytest.raises(TypeError):
            warehouse.merge(self.merge_source_table, "contract_test_table", None)

    def test_unsupported_merge_raises_rather_than_pretending(self, warehouse):
        # Java: ``unsupportedMergeThrowsRatherThanPretending``.
        if self.merge_supported:
            pytest.skip("backend supports merge")
        with pytest.raises(NotImplementedError, match="merge"):
            warehouse.merge(self.merge_source_table, "contract_test_table", ["id"])

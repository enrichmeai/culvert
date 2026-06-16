"""BigQueryWarehouse — Warehouse Protocol over google-cloud-bigquery.

Java sibling: ``com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse``.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, List, Mapping, Optional

logger = logging.getLogger(__name__)


class BigQueryWarehouse:
    """Cloud-neutral Warehouse adapter for Google BigQuery.

    Construction takes a pre-built ``google.cloud.bigquery.Client``; pass
    a Mockito-equivalent (e.g. ``unittest.mock.MagicMock``) in tests so
    no real GCP credentials are required.
    """

    def __init__(self, project_id: str, client: Any) -> None:
        if project_id is None:
            raise TypeError("project_id must not be None")
        if client is None:
            raise TypeError("client must not be None")
        self.project_id = project_id
        self.client = client

    def query(
        self,
        sql: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Iterator[Mapping[str, Any]]:
        """Execute a SELECT and stream rows as dicts.

        Argument validation is eager (runs before any iteration) so that
        ``query(None)`` raises immediately rather than only when the caller
        first iterates the returned generator.  This matches the Java
        contract (``nullSqlRejected``) and is required for
        ``WarehouseContract.test_null_sql_rejected``.
        """
        if sql is None:
            raise TypeError("sql must not be None")
        return self._query_rows(sql, params)

    def _query_rows(
        self,
        sql: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Iterator[Mapping[str, Any]]:
        """Inner generator — called only after sql has been validated."""
        # google-cloud-bigquery's QueryJobConfig accepts ScalarQueryParameter
        # but we pass dict-style params for the cloud-neutral surface and
        # let the caller stay loosely coupled. For full parameter typing,
        # the caller can build a QueryJobConfig themselves and pass it via
        # an extension (sprint-4 scope).
        job = self.client.query(sql)
        result = job.result()
        for row in result:
            # google-cloud-bigquery rows behave like dicts.
            yield dict(row.items()) if hasattr(row, "items") else dict(row)

    def execute(
        self,
        sql: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Execute DML/DDL. The job result is awaited but discarded."""
        if sql is None:
            raise TypeError("sql must not be None")
        job = self.client.query(sql)
        job.result()

    def load_from_uri(
        self,
        uri: str,
        target_table: str,
        schema: Any,
    ) -> int:
        """Bulk-load a GCS URI into a BigQuery table.

        Returns the number of rows loaded.
        """
        if uri is None or target_table is None:
            raise TypeError("uri and target_table must not be None")
        # Caller supplies a LoadJobConfig-shaped schema; for cloud-neutral
        # callers passing an EntitySchema, the caller is responsible for
        # converting it (sprint-4 auto-config will do that automatically).
        load_job = self.client.load_table_from_uri(uri, target_table, job_config=schema)
        load_job.result()
        return int(load_job.output_rows or 0)

    def merge(
        self,
        source_table: str,
        target_table: str,
        keys: List[str],
    ) -> int:
        """MERGE source into target on `keys`. Returns rows affected.

        Sprint-3 caveat: column-aware MERGE generation requires a schema
        lookup; that's sprint-4 scope. This raises NotImplementedError
        until then. Callers needing MERGE today should use ``execute()``
        with an explicit MERGE statement.
        """
        raise NotImplementedError(
            "merge() requires column-aware SQL generation (sprint-4 scope). "
            "Use execute(sql, params) with an explicit MERGE statement until then."
        )

    def copy(self, source_table: str, target_table: str) -> int:
        """Copy source_table to target_table; returns rows copied."""
        if source_table is None or target_table is None:
            raise TypeError("source_table and target_table must not be None")
        job = self.client.copy_table(source_table, target_table)
        job.result()
        # CopyJob doesn't expose a row count; report the target table's
        # post-copy row count.
        table = self.client.get_table(target_table)
        return int(getattr(table, "num_rows", 0) or 0)

    def table_exists(self, fqtn: str) -> bool:
        """Return True if a table at `fqtn` exists."""
        if fqtn is None:
            raise TypeError("fqtn must not be None")
        try:
            self.client.get_table(fqtn)
            return True
        except Exception:
            # google.api_core.exceptions.NotFound — we catch broadly to
            # stay decoupled from the specific GCP exception import.
            return False

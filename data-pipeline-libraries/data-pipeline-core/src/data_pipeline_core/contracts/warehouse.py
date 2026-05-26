"""Warehouse — tabular query/load abstraction.

Deliberately conservative — only the six operations every serious
warehouse supports. Cloud-specific operations (BigQuery clustering,
partitioning, BI Engine, slot-aware predicates; Redshift sortkeys;
Snowflake clustering keys; Synapse distribution) are exposed via a
cloud-specific extension class in the cloud module (e.g.
`data_pipeline_gcp_bigquery.BigQueryExtensions`).

This deliberately omits `write_to_table(data: List[dict])` and
`read_table() -> DataFrame` that the existing BigQueryClient exposes,
because they are warehouse-shaped in BigQuery's idiom (and DataFrames
are pandas-coupled). Those stay on `BigQueryWarehouse` as the
implementation's surface, not on the Protocol.
"""

from __future__ import annotations

from typing import Any, Iterator, List, Mapping, Optional, Protocol, runtime_checkable

from data_pipeline_core.schema.entity import EntitySchema


@runtime_checkable
class Warehouse(Protocol):
    """Tabular query/load abstraction. URIs and fully-qualified table
    names (`fqtn`) are opaque strings; the implementation parses them
    according to its own conventions (`project.dataset.table` for
    BigQuery; `database.schema.table` for Redshift/Snowflake;
    `database.dbo.table` for Synapse).
    """

    def query(
        self,
        sql: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Iterator[Mapping[str, Any]]:
        """Execute a SELECT and stream rows as dicts.

        Implementations should not buffer the entire result in memory;
        iterating the result must be lazy.
        """
        ...

    def execute(
        self,
        sql: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Execute a DML/DDL statement that does not return rows
        (INSERT, UPDATE, MERGE, CREATE, DROP, ALTER).
        """
        ...

    def load_from_uri(
        self,
        uri: str,
        target_table: str,
        schema: EntitySchema,
    ) -> int:
        """Bulk-load an object at `uri` into `target_table`.

        Returns the number of rows loaded. `uri` is a BlobStore URI
        (`gs://`, `s3://`, ...) — the warehouse implementation is
        responsible for arranging access (same-cloud loads only;
        cross-cloud loads are out of scope, see redesign Q4).
        """
        ...

    def merge(
        self,
        source_table: str,
        target_table: str,
        keys: List[str],
    ) -> int:
        """MERGE source into target on `keys`. Returns rows affected.

        Standard upsert semantics: matched rows are updated, unmatched
        source rows are inserted, target rows missing from source are
        left alone.
        """
        ...

    def copy(self, source_table: str, target_table: str) -> int:
        """Copy `source_table` to `target_table`. Returns rows copied.

        Should be a metadata-only operation where the warehouse
        supports it (BigQuery CREATE TABLE COPY, Snowflake CLONE).
        """
        ...

    def table_exists(self, fqtn: str) -> bool:
        """Return True if a table at `fqtn` exists."""
        ...

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

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, List, Mapping, Optional, Protocol, runtime_checkable

from data_pipeline_core.schema.entity import EntitySchema


class WriteDisposition(Enum):
    """What a load does to data already present in the target."""

    APPEND = "append"
    """Add rows, keeping everything already there.

    Not idempotent: loading the same source twice yields two copies.
    Correct for genuinely additive feeds, wrong for re-runnable batch
    extracts — which is the case that made this enum necessary.
    """

    TRUNCATE = "truncate"
    """Replace the target's existing rows with the loaded ones.

    Scoped to ``LoadOptions.target_partition`` when one is given, and to
    the whole table when one is not — so a TRUNCATE without a partition
    on a multi-extract table destroys the other extracts. Implementations
    must not silently narrow this.
    """

    ERROR_IF_EXISTS = "error_if_exists"
    """Load only into an empty target; fail rather than write otherwise."""


@dataclass(frozen=True)
class LoadOptions:
    """How a :meth:`Warehouse.load_from_uri` call should write into its target.

    Before this type, ``load_from_uri`` carried no way to say what should
    happen to data already in the target, so every backend was free to pick
    — and picked differently. The Java ``BigQueryWarehouse`` built a
    ``LoadJobConfiguration`` with only a schema and a format, which meant
    BigQuery applied its own default of ``WRITE_APPEND``: re-running the
    same extract silently doubled the data.

    The fix is deliberately **not** a defaulted parameter. A default is
    exactly what caused the bug — it lets a caller write an
    idempotency-critical load without ever deciding what "re-run" means.

    ``target_partition`` names a single partition to confine the write to,
    so TRUNCATE can mean "replace just this partition". It is an opaque,
    backend-parsed string for the same reason ``fqtn`` is.

    Honest limitation: partition-scoped replace only helps when the table is
    partitioned by the column that identifies a load. A table partitioned on
    a *business* date cannot express "replace this extract" as a partition
    operation, because one extract spans many business dates.

    Python mirror of the Java ``com.enrichmeai.culvert.contracts.LoadOptions``
    record.
    """

    write_disposition: WriteDisposition
    target_partition: Optional[str] = None

    @staticmethod
    def append() -> "LoadOptions":
        """Add rows, keeping what is already there."""
        return LoadOptions(WriteDisposition.APPEND)

    @staticmethod
    def truncate() -> "LoadOptions":
        """Replace the whole target table."""
        return LoadOptions(WriteDisposition.TRUNCATE)

    @staticmethod
    def truncate_partition(partition_id: str) -> "LoadOptions":
        """Replace only ``partition_id`` within the target."""
        return LoadOptions(WriteDisposition.TRUNCATE, partition_id)

    @staticmethod
    def error_if_exists() -> "LoadOptions":
        """Load only into an empty target."""
        return LoadOptions(WriteDisposition.ERROR_IF_EXISTS)


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
        options: LoadOptions,
    ) -> int:
        """Bulk-load an object at `uri` into `target_table`.

        Returns the number of rows loaded. `uri` is a BlobStore URI
        (`gs://`, `s3://`, ...) — the warehouse implementation is
        responsible for arranging access (same-cloud loads only;
        cross-cloud loads are out of scope, see redesign Q4).

        `options` is **required**, and there is deliberately no
        defaulted variant. The earlier signature had no disposition
        parameter at all, so each backend silently chose one — BigQuery's
        own default of WRITE_APPEND — and re-running an extract quietly
        doubled the data. A default would preserve exactly that failure.

        Implementations that cannot honour the requested disposition must
        raise ``NotImplementedError`` naming it — never silently downgrade
        to APPEND, which is the bug this parameter exists to prevent.
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

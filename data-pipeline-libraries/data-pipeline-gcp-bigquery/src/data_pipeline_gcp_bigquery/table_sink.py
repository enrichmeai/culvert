"""``BigQueryTableSink`` — a ``Sink`` that loads records into a BigQuery table (#13).

It uses batch load jobs (``Client.load_table_from_json``), not streaming
inserts: a load job is all or nothing, leaves no streaming buffer, and costs
nothing per row. Each batch of up to ``batch_size`` records is one load job,
waited on before the next; a failed job raises, so the run stops there with
the earlier batches loaded and none of the failed one. A run that failed
partway is therefore re-run with ``WRITE_TRUNCATE`` or against a table the
next stage de-duplicates.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import math
import re
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence

# project (optionally domain-scoped, "example.com:project"), dataset, table
_TABLE = re.compile(
    r"^(?:((?:[A-Za-z0-9.-]+:)?[A-Za-z0-9_-]+)\.)?([A-Za-z0-9_]+)\.([A-Za-z0-9_$-]+)$")
_DISPOSITIONS = ("WRITE_APPEND", "WRITE_TRUNCATE", "WRITE_EMPTY")


class BigQueryTableSink:
    """Load mapping records into ``table`` (``project.dataset.table`` or ``dataset.table``).

    Args:
        table: The destination table. A table that does not exist is created
            on the first load (BigQuery's ``CREATE_IF_NEEDED``); without a
            ``schema``, the client lets BigQuery detect one.
        client: A ``google.cloud.bigquery.Client``. Default: one made on the
            first write with Application Default Credentials, for the table's
            project (or the default project when the table names none).
        write_disposition: ``WRITE_APPEND`` (default), ``WRITE_TRUNCATE`` or
            ``WRITE_EMPTY``. It applies to the first batch; later batches of the
            same write append, so a truncating write replaces the table once.
            No records means no load job: an empty truncating write leaves the
            table as it was.
        batch_size: Records per load job. Default 10 000.
        schema: Optional ``SchemaField`` list for the load job. Without one,
            a new table's schema is detected from the first batch alone, and
            later batches must fit it: pass a schema for production tables.

    ``datetime``/``date``/``time`` values are sent as ISO 8601 strings and
    ``Decimal`` as a string, which BigQuery parses for the matching column
    types. A value JSON cannot carry (NaN or infinity, bytes, a set, any other
    object) raises ``ValueError`` before its batch is sent.
    """

    def __init__(self, table: str, *, client: Any = None,
                 write_disposition: str = "WRITE_APPEND", batch_size: int = 10_000,
                 schema: Optional[Sequence[Any]] = None) -> None:
        match = _TABLE.match(table or "")
        if not match:
            raise ValueError(f"BigQueryTableSink table must be project.dataset.table or "
                             f"dataset.table, got {table!r}")
        if write_disposition not in _DISPOSITIONS:
            raise ValueError(f"write_disposition must be one of {_DISPOSITIONS}, "
                             f"got {write_disposition!r}")
        if isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError(f"batch_size must be a positive int, got {batch_size!r}")
        self.table = table
        self._project = match.group(1)
        self._client = client
        self._disposition = write_disposition
        self._batch_size = batch_size
        self._schema = list(schema) if schema is not None else None

    def write(self, records: Iterable[Mapping[str, Any]], context: Any) -> None:
        from google.cloud import bigquery

        disposition = self._disposition
        for batch in _batches(records, self._batch_size):
            config = bigquery.LoadJobConfig(write_disposition=disposition)
            if self._schema is not None:
                config.schema = self._schema
            job = self._client_for_write().load_table_from_json(
                batch, self.table, job_config=config)
            job.result()  # waits; raises if the job failed
            disposition = "WRITE_APPEND"

    def _client_for_write(self) -> Any:
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self._project)
        return self._client


def _batches(records: Iterable[Mapping[str, Any]], size: int) -> Iterator[List[dict]]:
    batch: List[dict] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise TypeError(f"BigQueryTableSink needs mapping records, got {type(record).__name__}")
        batch.append({k: _json_value(v, k) for k, v in record.items()})
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _json_value(value: Any, field: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"BigQueryTableSink: field '{field}' is {value}, which JSON cannot "
                             f"carry; map it to None or a number first")
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        if not value.is_finite():
            raise ValueError(f"BigQueryTableSink: field '{field}' is {value}, which JSON cannot "
                             f"carry")
        return str(value)
    if isinstance(value, Mapping):
        return {k: _json_value(v, f"{field}.{k}") for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v, field) for v in value]
    raise ValueError(f"BigQueryTableSink: field '{field}' is a {type(value).__name__}, which "
                     f"cannot be loaded as JSON; convert it first (bytes: base64 text)")


__all__ = ["BigQueryTableSink"]

"""BigQueryFinOpsSink — FinOpsSink Protocol backed by BigQuery streaming inserts.

Java sibling: ``com.enrichmeai.culvert.gcp.bigquery.BigQueryFinOpsSink``
(data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/
com/enrichmeai/culvert/gcp/bigquery/BigQueryFinOpsSink.java)

Each call to :meth:`record` streams a single row into the configured
``cost_metrics`` table via ``insert_rows_json``, BigQuery's Python-SDK
equivalent of the Java ``insertAll`` API.

Sprint-19 / T19.3 deliverable for issue #126.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional

from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics

logger = logging.getLogger(__name__)

# Default table name — matches Java BigQueryFinOpsSink.DEFAULT_TABLE (line 60).
DEFAULT_TABLE = "cost_metrics"


class BigQueryFinOpsSink:
    """FinOpsSink implementation backed by Google Cloud BigQuery streaming inserts.

    Mirrors ``com.enrichmeai.culvert.gcp.bigquery.BigQueryFinOpsSink``.

    Each :meth:`record` call streams a single row into the configured
    ``cost_metrics`` table. The row carries every field from both
    :class:`~data_pipeline_core.finops_api.models.CostMetrics` and
    :class:`~data_pipeline_core.finops_api.labels.FinOpsTag`, flattened into
    table columns. ``labels`` and ``extra`` are represented as
    ``[{"key": k, "value": v}]`` lists (BigQuery's stable RECORD<key,value>
    array pattern — no DDL change per new label key).

    **Partial failures**: ``insert_rows_json`` can succeed at the request
    level while reporting per-row errors. Any non-empty error list raises
    :class:`FinOpsInsertException` — silently dropping cost rows would defeat
    the FinOps audit trail (mirrors Java lines 101-103).

    **Construction**: pass a pre-built ``google.cloud.bigquery.Client``,
    project ID, dataset, and table name. The client is not closed by this
    class (``google-cloud-bigquery`` 3.x clients are not context managers).
    """

    def __init__(
        self,
        client: Any,
        project_id: str,
        dataset: str,
        table: str = DEFAULT_TABLE,
    ) -> None:
        """
        :param client:     Pre-built ``google.cloud.bigquery.Client``. Required.
        :param project_id: GCP project ID. Required.
        :param dataset:    BigQuery dataset name. Required.
        :param table:      BigQuery table name. Defaults to ``"cost_metrics"``.
        :raises TypeError: if any required argument is None.
        """
        if client is None:
            raise TypeError("client must not be None")
        if project_id is None:
            raise TypeError("project_id must not be None")
        if dataset is None:
            raise TypeError("dataset must not be None")
        if table is None:
            raise TypeError("table must not be None")

        self._client = client
        self._project_id = project_id
        self._dataset = dataset
        self._table = table

    # --- FinOpsSink Protocol ------------------------------------------------

    def record(self, metrics: CostMetrics, tags: FinOpsTag) -> None:
        """Stream one cost-metrics row to BigQuery.

        Mirrors Java ``BigQueryFinOpsSink.record`` (lines 92-104).

        :raises TypeError: if metrics or tags is None.
        :raises FinOpsInsertException: if BigQuery returns per-row errors.
        """
        if metrics is None:
            raise TypeError("metrics must not be None")
        if tags is None:
            raise TypeError("tags must not be None")

        table_ref = f"{self._project_id}.{self._dataset}.{self._table}"
        row = self._to_row(metrics, tags)
        errors = self._client.insert_rows_json(table_ref, [row])
        if errors:
            raise FinOpsInsertException(metrics.run_id, errors)

    # --- internal helpers ---------------------------------------------------

    def _to_row(self, metrics: CostMetrics, tags: FinOpsTag) -> Dict[str, Any]:
        """Build the wire row dict.

        Field ordering mirrors Java ``BigQueryFinOpsSink.toRow`` (lines 113-141):
        FinOpsTag attribution columns first (cost-allocation key), then
        CostMetrics columns.
        """
        row: Dict[str, Any] = {}
        # FinOpsTag attribution columns — mirrors Java lines 116-123.
        row["system"] = tags.system
        row["environment"] = tags.environment
        row["cost_center"] = tags.cost_center
        row["owner"] = tags.owner
        row["tag_run_id"] = tags.run_id
        row["tag_extra"] = _flatten_map(tags.extra)

        # CostMetrics columns — mirrors Java lines 126-139.
        row["run_id"] = metrics.run_id
        row["estimated_cost_usd"] = metrics.estimated_cost_usd
        row["billed_bytes_scanned"] = metrics.billed_bytes_scanned
        row["billed_bytes_written"] = metrics.billed_bytes_written
        row["billed_bytes_stored"] = metrics.billed_bytes_stored
        row["billed_messages_count"] = metrics.billed_messages_count
        row["slot_millis"] = metrics.slot_millis
        row["compute_units"] = metrics.compute_units
        row["labels"] = _flatten_map(metrics.labels)
        # ISO-8601 string — BigQuery TIMESTAMP accepts it (mirrors Java line 138).
        row["timestamp"] = metrics.timestamp.isoformat()

        return row


def _flatten_map(mapping: Optional[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Flatten a str→str mapping into ``[{"key": k, "value": v}]`` records.

    Mirrors Java ``BigQueryFinOpsSink.flattenMap`` (lines 149-161).
    """
    if not mapping:
        return []
    return [{"key": k, "value": v} for k, v in mapping.items()]


class FinOpsInsertException(RuntimeError):
    """Raised when BigQuery's streaming insert returns per-row errors.

    Mirrors Java ``BigQueryFinOpsSink.FinOpsInsertException`` (lines 168-180).
    """

    def __init__(self, run_id: str, insert_errors: list) -> None:
        n = len(insert_errors)
        super().__init__(
            f"BigQuery streaming insert returned errors for run_id={run_id!r} "
            f"({n} row(s) failed)"
        )
        self.insert_errors = insert_errors
        self.run_id = run_id

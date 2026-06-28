"""BigQueryCostTracker — builds CostMetrics from BigQuery job statistics.

Java sibling: ``com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker``
(data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/
com/enrichmeai/culvert/gcp/bigquery/BigQueryCostTracker.java)

Mirrors the Java constants and formulas exactly:

- ``BYTES_PER_TIB = 1_099_511_627_776``  (2^40, Java line 81)
- ``QUERY_COST_USD_PER_TIB = 5.00``      (Java line 90)
- ``LOAD_COST_USD_PER_TIB  = 0.01``      (Java line 103)
- Formula: ``estimatedCostUsd = bytes / BYTES_PER_TIB * rate``
  (Java ``bytesToUsd``, lines 321-326)

Sprint-19 / T19.3 deliverable for issue #126.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing constants — mirror Java BigQueryCostTracker exactly
# ---------------------------------------------------------------------------

#: Bytes in one tebibyte (2^40).
#:
#: BigQuery on-demand pricing uses the binary definition of terabyte.
#: Use this constant — not 1e12 — to avoid an ~10% undercount in estimates.
#:
#: Java source: ``BigQueryCostTracker.BYTES_PER_TIB = 1_099_511_627_776L``
#: (data-pipeline-gcp-bigquery-java/.../BigQueryCostTracker.java, line 81)
BYTES_PER_TIB: int = 1_099_511_627_776  # 2^40

#: BigQuery on-demand query cost in USD per TiB scanned.
#:
#: Rate as of 2025: $5.00/TiB for on-demand queries.
#:
#: Java source: ``BigQueryCostTracker.QUERY_COST_USD_PER_TIB = 5.00``
#: (data-pipeline-gcp-bigquery-java/.../BigQueryCostTracker.java, line 90)
QUERY_COST_USD_PER_TIB: float = 5.00

#: Load cost constant in USD per TiB written — GCS-egress-equivalent
#: accounting rate, not an actual BigQuery ingest charge.
#:
#: Java source: ``BigQueryCostTracker.LOAD_COST_USD_PER_TIB = 0.01``
#: (data-pipeline-gcp-bigquery-java/.../BigQueryCostTracker.java, line 103)
LOAD_COST_USD_PER_TIB: float = 0.01


class BigQueryCostTracker:
    """Reads job statistics from a completed BigQuery job, builds a
    :class:`~data_pipeline_core.finops_api.models.CostMetrics` record, and
    pushes it to the injected :class:`~data_pipeline_core.contracts.finops.FinOpsSink`.

    Supported job types (mirrors Java Javadoc lines 22-30):
    - **Query jobs**: ``totalBytesBilled`` → ``billed_bytes_scanned``;
      ``totalSlotMs`` → ``slot_millis``.
    - **Load jobs**: ``outputBytes`` → ``billed_bytes_written``.
    - **Other jobs**: slot_millis only; zero cost.

    Cost formula for query jobs (mirrors Java lines 243-248)::

        estimated_cost_usd = billed_bytes_scanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB

    Cost formula for load jobs (mirrors Java lines 252-258)::

        estimated_cost_usd = billed_bytes_written / BYTES_PER_TIB * LOAD_COST_USD_PER_TIB

    This class does NOT hold its own client for dry-run support (that path
    requires a real BigQuery client and is an optional method). Pass the
    same ``client`` used to submit jobs.

    :param client: Pre-built ``google.cloud.bigquery.Client``. Required.
    :param sink:   FinOps sink that receives the built CostMetrics. Required.
    :raises TypeError: if either argument is None.
    """

    def __init__(self, client: Any, sink: FinOpsSink) -> None:
        if client is None:
            raise TypeError("client must not be None")
        if sink is None:
            raise TypeError("sink must not be None")
        self._client = client
        self._sink = sink

    # --- public API ---------------------------------------------------------

    def track_job(self, job: Any, run_id: str, tag: FinOpsTag) -> None:
        """Extract cost metrics from a completed BigQuery job and emit via sink.

        Mirrors Java ``BigQueryCostTracker.trackJob`` (lines 138-165).

        :param job:    Completed BigQuery job object. Required.
        :param run_id: Pipeline run identifier. Required.
        :param tag:    FinOps attribution tag. Required.
        :raises TypeError: if job, run_id, or tag is None.
        """
        if job is None:
            raise TypeError("job must not be None")
        if run_id is None:
            raise TypeError("run_id must not be None")
        if tag is None:
            raise TypeError("tag must not be None")

        # Retrieve statistics from the job object.  The google-cloud-bigquery
        # SDK exposes these on the Job object; we duck-type to avoid a hard
        # import of the GCP types (mirrors Java's cast-based dispatch).
        stats = self._get_stats(job, run_id)
        if stats is None:
            return

        job_type = getattr(stats, "job_type", None) or _infer_job_type(stats)

        if job_type == "QUERY":
            metrics = self._build_from_query_stats(stats, run_id)
        elif job_type == "LOAD":
            metrics = self._build_from_load_stats(stats, run_id)
        else:
            # Copy / Extract / Script — zero-cost record with slot_millis.
            slot_millis = _safe_slot_ms(stats, run_id)
            metrics = CostMetrics(run_id=run_id, slot_millis=slot_millis)

        self._sink.record(metrics, tag)

    # --- private helpers ----------------------------------------------------

    @staticmethod
    def _get_stats(job: Any, run_id: str) -> Optional[Any]:
        """Return job statistics object, logging WARN and returning None if absent."""
        stats = None
        # google-cloud-bigquery 3.x: job._properties["statistics"] or job.statistics()
        if hasattr(job, "_job_statistics"):
            stats = job._job_statistics()
        elif hasattr(job, "statistics"):
            stats = job.statistics
        if stats is None:
            logger.warning(
                "BigQueryCostTracker: job has null statistics — cost metrics not emitted "
                "(run_id=%s)", run_id,
            )
        return stats

    @staticmethod
    def _build_from_query_stats(stats: Any, run_id: str) -> CostMetrics:
        """Build CostMetrics from QueryStatistics. Mirrors Java lines 238-249."""
        bytes_scanned = _safe_bytes_scanned(stats, run_id)
        slot_millis = _safe_slot_ms(stats, run_id)
        cost_usd = _bytes_to_usd(bytes_scanned, QUERY_COST_USD_PER_TIB)
        return CostMetrics(
            run_id=run_id,
            billed_bytes_scanned=bytes_scanned,
            slot_millis=slot_millis,
            estimated_cost_usd=cost_usd,
        )

    @staticmethod
    def _build_from_load_stats(stats: Any, run_id: str) -> CostMetrics:
        """Build CostMetrics from LoadStatistics. Mirrors Java lines 252-259."""
        bytes_written = _safe_output_bytes(stats, run_id)
        cost_usd = _bytes_to_usd(bytes_written, LOAD_COST_USD_PER_TIB)
        return CostMetrics(
            run_id=run_id,
            billed_bytes_written=bytes_written,
            estimated_cost_usd=cost_usd,
        )


# ---------------------------------------------------------------------------
# Module-level formula helpers (used by tests to verify the unit chain)
# ---------------------------------------------------------------------------

def bytes_to_usd(bytes_count: int, cost_per_tib: float) -> float:
    """Convert bytes to USD at the given per-TiB rate.

    Mirrors Java ``BigQueryCostTracker.bytesToUsd`` (lines 321-326)::

        return (double) bytes / (double) BYTES_PER_TIB * costPerTib;

    Zero or negative input returns 0.0 (mirrors Java guard on line 323).
    """
    if bytes_count <= 0:
        return 0.0
    return bytes_count / BYTES_PER_TIB * cost_per_tib


# Internal alias used inside the class (avoids name collision with self).
_bytes_to_usd = bytes_to_usd


def _safe_bytes_scanned(stats: Any, run_id: str) -> int:
    """Extract totalBytesBilled, treating None as 0 + WARN (mirrors Java lines 263-270)."""
    v = getattr(stats, "total_bytes_billed", None)
    if v is None:
        logger.warning(
            "BigQueryCostTracker: total_bytes_billed is None for run_id=%s — treating as 0",
            run_id,
        )
        return 0
    return int(v)


def _safe_slot_ms(stats: Any, run_id: str) -> int:
    """Extract totalSlotMs, treating None as 0 + WARN (mirrors Java lines 273-280)."""
    v = getattr(stats, "total_slot_ms", None)
    if v is None:
        logger.warning(
            "BigQueryCostTracker: total_slot_ms is None for run_id=%s — treating as 0",
            run_id,
        )
        return 0
    return int(v)


def _safe_output_bytes(stats: Any, run_id: str) -> int:
    """Extract outputBytes from LoadStatistics, treating None as 0 + WARN (mirrors Java lines 285-292)."""
    v = getattr(stats, "output_bytes", None)
    if v is None:
        logger.warning(
            "BigQueryCostTracker: output_bytes is None for run_id=%s — treating as 0",
            run_id,
        )
        return 0
    return int(v)


def _infer_job_type(stats: Any) -> str:
    """Infer job type from statistics attributes when job_type is not present."""
    if hasattr(stats, "total_bytes_billed"):
        return "QUERY"
    if hasattr(stats, "output_bytes"):
        return "LOAD"
    return "OTHER"

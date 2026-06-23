"""GcsCostTracker — builds CostMetrics from GCS operation byte counts.

Java sibling: ``com.enrichmeai.culvert.gcp.gcs.GcsCostTracker``
(data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/
com/enrichmeai/culvert/gcp/gcs/GcsCostTracker.java)

Mirrors the Java constants and formulas exactly:

- ``BYTES_PER_GIB = 1_073_741_824``         (2^30, Java line 77)
- ``WRITE_COST_USD_PER_GIB = 0.01``          (Java line 90)
- ``STANDARD_STORAGE_USD_PER_GIB = 0.020``   (Java line 99)
- ``NEARLINE_STORAGE_USD_PER_GIB = 0.010``   (Java line 108)
- ``COLDLINE_STORAGE_USD_PER_GIB = 0.004``   (Java line 117)
- ``ARCHIVE_STORAGE_USD_PER_GIB  = 0.0012``  (Java line 126)

Upload formula (Java lines 162-163)::

    estimated_cost_usd = bytes_written / BYTES_PER_GIB * WRITE_COST_USD_PER_GIB

Storage formula (Java lines 206-208)::

    estimated_cost_usd = bytes_stored / BYTES_PER_GIB * rate_for_class

Sprint-19 / T19.3 deliverable for issue #126.
"""

from __future__ import annotations

import logging

from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing constants — mirror Java GcsCostTracker exactly
# ---------------------------------------------------------------------------

#: Bytes in one gibibyte (2^30).
#:
#: GCS storage pricing is quoted in GiB-months (binary definition).
#: Use this constant — not 1e9 — to avoid an ~7% undercount.
#:
#: Java source: ``GcsCostTracker.BYTES_PER_GIB = 1_073_741_824L``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 77)
BYTES_PER_GIB: int = 1_073_741_824  # 2^30

#: GCS upload cost accounting placeholder in USD per GiB written.
#:
#: Note: GCS does not bill per-byte for write operations (Class A per-10k).
#: This is an accounting placeholder.
#:
#: Java source: ``GcsCostTracker.WRITE_COST_USD_PER_GIB = 0.01``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 90)
WRITE_COST_USD_PER_GIB: float = 0.01

#: GCS Standard storage rate in USD per GiB-month (US multi-region, 2025).
#:
#: Java source: ``GcsCostTracker.STANDARD_STORAGE_USD_PER_GIB = 0.020``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 99)
STANDARD_STORAGE_USD_PER_GIB: float = 0.020

#: GCS Nearline storage rate in USD per GiB-month (US multi-region, 2025).
#:
#: Java source: ``GcsCostTracker.NEARLINE_STORAGE_USD_PER_GIB = 0.010``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 108)
NEARLINE_STORAGE_USD_PER_GIB: float = 0.010

#: GCS Coldline storage rate in USD per GiB-month (US multi-region, 2025).
#:
#: Java source: ``GcsCostTracker.COLDLINE_STORAGE_USD_PER_GIB = 0.004``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 117)
COLDLINE_STORAGE_USD_PER_GIB: float = 0.004

#: GCS Archive storage rate in USD per GiB-month (US multi-region, 2025).
#:
#: Java source: ``GcsCostTracker.ARCHIVE_STORAGE_USD_PER_GIB = 0.0012``
#: (data-pipeline-gcp-gcs-java/.../GcsCostTracker.java, line 126)
ARCHIVE_STORAGE_USD_PER_GIB: float = 0.0012


class GcsCostTracker:
    """Builds a :class:`~data_pipeline_core.finops_api.models.CostMetrics` record
    from GCS operation sizes and pushes it to the injected
    :class:`~data_pipeline_core.contracts.finops.FinOpsSink`.

    Mirrors ``com.enrichmeai.culvert.gcp.gcs.GcsCostTracker``.

    This class does NOT hold a GCS client — it operates on byte counts
    already obtained by the caller (from a GCS API response).

    Supported operations:

    - :meth:`track_upload`: records ``billed_bytes_written``; estimates USD
      using :data:`WRITE_COST_USD_PER_GIB`.
    - :meth:`track_storage_class`: records ``billed_bytes_stored``; estimates
      monthly storage USD at per-class rates.

    :param sink: FinOps sink that receives the built CostMetrics. Required.
    :raises TypeError: if sink is None.
    """

    def __init__(self, sink: FinOpsSink) -> None:
        if sink is None:
            raise TypeError("sink must not be None")
        self._sink = sink

    # --- public API ---------------------------------------------------------

    def track_upload(self, bytes_written: int, run_id: str, tag: FinOpsTag) -> None:
        """Record cost metrics for a GCS upload operation.

        Mirrors Java ``GcsCostTracker.trackUpload`` (lines 153-171).

        Formula (mirrors Java lines 162-163)::

            estimated_cost_usd = bytes_written / BYTES_PER_GIB * WRITE_COST_USD_PER_GIB

        Zero or negative ``bytes_written`` logs WARN and records zero cost;
        :meth:`FinOpsSink.record` is called exactly once.

        :param bytes_written: Number of bytes written in the upload.
        :param run_id:        Pipeline run identifier.
        :param tag:           FinOps attribution tag.
        :raises TypeError: if run_id or tag is None.
        """
        if run_id is None:
            raise TypeError("run_id must not be None")
        if tag is None:
            raise TypeError("tag must not be None")

        if bytes_written <= 0:
            logger.warning(
                "GcsCostTracker.track_upload: bytes_written=%d for run_id=%s "
                "— recording zero cost", bytes_written, run_id,
            )

        billed = max(0, bytes_written)
        cost_usd = _bytes_to_usd(billed, WRITE_COST_USD_PER_GIB)

        metrics = CostMetrics(
            run_id=run_id,
            billed_bytes_written=billed,
            estimated_cost_usd=cost_usd,
        )
        self._sink.record(metrics, tag)

    def track_storage_class(
        self,
        bytes_stored: int,
        storage_class: str,
        run_id: str,
        tag: FinOpsTag,
    ) -> None:
        """Record cost metrics for bytes stored under a given GCS storage class.

        Mirrors Java ``GcsCostTracker.trackStorageClass`` (lines 195-215).

        Recognised storage class strings (case-insensitive):
        ``STANDARD``, ``NEARLINE``, ``COLDLINE``, ``ARCHIVE``.
        An unrecognised class falls back to Standard and logs WARN
        (mirrors Java lines 235-239).

        Formula (mirrors Java lines 206-208)::

            estimated_cost_usd = bytes_stored / BYTES_PER_GIB * rate_for_class

        :param bytes_stored:  Number of bytes stored.
        :param storage_class: GCS storage class (e.g. ``"STANDARD"``).
                              Case-insensitive. None treated as unknown.
        :param run_id:        Pipeline run identifier.
        :param tag:           FinOps attribution tag.
        :raises TypeError: if run_id or tag is None.
        """
        if run_id is None:
            raise TypeError("run_id must not be None")
        if tag is None:
            raise TypeError("tag must not be None")

        if bytes_stored <= 0:
            logger.warning(
                "GcsCostTracker.track_storage_class: bytes_stored=%d for run_id=%s "
                "— recording zero cost", bytes_stored, run_id,
            )

        rate = _resolve_storage_rate(storage_class, run_id)
        billed = max(0, bytes_stored)
        cost_usd = _bytes_to_usd(billed, rate)

        metrics = CostMetrics(
            run_id=run_id,
            billed_bytes_stored=billed,
            estimated_cost_usd=cost_usd,
        )
        self._sink.record(metrics, tag)


# ---------------------------------------------------------------------------
# Module-level formula helpers (used by tests to verify the unit chain)
# ---------------------------------------------------------------------------

def bytes_to_usd(bytes_count: int, rate_per_gib: float) -> float:
    """Convert bytes to USD at the given per-GiB rate.

    Mirrors Java ``GcsCostTracker.bytesToUsd`` (lines 244-248)::

        return (double) bytes / (double) BYTES_PER_GIB * ratePerGib;

    Zero or negative input returns 0.0 (mirrors Java guard on line 246).
    """
    if bytes_count <= 0:
        return 0.0
    return bytes_count / BYTES_PER_GIB * rate_per_gib


# Internal alias used inside the class.
_bytes_to_usd = bytes_to_usd


def _resolve_storage_rate(storage_class: str, run_id: str) -> float:
    """Resolve per-GiB-month rate for a given storage class string.

    Mirrors Java ``GcsCostTracker.resolveStorageRate`` (lines 224-240).
    Falls back to STANDARD and logs WARN on unknown/None input.
    """
    if storage_class is None:
        logger.warning(
            "GcsCostTracker.track_storage_class: None storage_class for run_id=%s "
            "— defaulting to STANDARD rate", run_id,
        )
        return STANDARD_STORAGE_USD_PER_GIB

    key = storage_class.upper()
    rates = {
        "STANDARD": STANDARD_STORAGE_USD_PER_GIB,
        "NEARLINE":  NEARLINE_STORAGE_USD_PER_GIB,
        "COLDLINE":  COLDLINE_STORAGE_USD_PER_GIB,
        "ARCHIVE":   ARCHIVE_STORAGE_USD_PER_GIB,
    }
    rate = rates.get(key)
    if rate is None:
        logger.warning(
            "GcsCostTracker.track_storage_class: unknown storage_class=%r for run_id=%s "
            "— defaulting to STANDARD rate", storage_class, run_id,
        )
        return STANDARD_STORAGE_USD_PER_GIB
    return rate

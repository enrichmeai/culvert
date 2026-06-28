"""PubSubCostTracker — builds CostMetrics from Pub/Sub message counts and bytes.

Java sibling: ``com.enrichmeai.culvert.gcp.pubsub.PubSubCostTracker``
(data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/
com/enrichmeai/culvert/gcp/pubsub/PubSubCostTracker.java)

Mirrors the Java constants and formula exactly:

- ``BYTES_PER_TIB = 1_099_511_627_776``    (2^40, Java line 65)
- ``THROUGHPUT_COST_USD_PER_TIB = 40.00``  (Java line 81)

Formula for publish and subscribe (Java lines 125, 186)::

    estimated_cost_usd = total_bytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB

``message_count`` maps to ``billed_messages_count`` for attribution;
it does NOT drive the USD estimate because Pub/Sub bills on throughput bytes
(mirrors Java Javadoc lines 35-37).

Sprint-19 / T19.3 deliverable for issue #126.
"""

from __future__ import annotations

import logging

from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing constants — mirror Java PubSubCostTracker exactly
# ---------------------------------------------------------------------------

#: Bytes in one tebibyte (2^40).
#:
#: Pub/Sub pricing uses binary TiB. Mirrors BigQueryCostTracker.BYTES_PER_TIB.
#: Use this constant — not 1e12 — to avoid an ~10% undercount.
#:
#: Java source: ``PubSubCostTracker.BYTES_PER_TIB = 1_099_511_627_776L``
#: (data-pipeline-gcp-pubsub-java/.../PubSubCostTracker.java, line 65)
BYTES_PER_TIB: int = 1_099_511_627_776  # 2^40

#: Pub/Sub message throughput cost in USD per TiB.
#:
#: Rate as of 2025: $40.00/TiB of message data throughput.
#: The first 10 GiB/month is free; this constant is the on-demand rate
#: above the free tier (no free-tier deduction applied here).
#:
#: Java source: ``PubSubCostTracker.THROUGHPUT_COST_USD_PER_TIB = 40.00``
#: (data-pipeline-gcp-pubsub-java/.../PubSubCostTracker.java, line 81)
THROUGHPUT_COST_USD_PER_TIB: float = 40.00


class PubSubCostTracker:
    """Builds a :class:`~data_pipeline_core.finops_api.models.CostMetrics` record
    from Pub/Sub message-count and throughput-bytes, and pushes it to the
    injected :class:`~data_pipeline_core.contracts.finops.FinOpsSink`.

    Mirrors ``com.enrichmeai.culvert.gcp.pubsub.PubSubCostTracker``.

    This class does NOT hold a Pub/Sub client — it operates on message counts
    and byte counts already obtained by the caller.

    Supported operations:

    - :meth:`track_publish`:   publish batch cost (mirrors Java lines 110-134).
    - :meth:`track_subscribe`: subscribe batch cost (mirrors Java lines 153-177).

    :param sink: FinOps sink that receives the built CostMetrics. Required.
    :raises TypeError: if sink is None.
    """

    def __init__(self, sink: FinOpsSink) -> None:
        if sink is None:
            raise TypeError("sink must not be None")
        self._sink = sink

    # --- public API ---------------------------------------------------------

    def track_publish(
        self,
        message_count: int,
        total_bytes: int,
        run_id: str,
        tag: FinOpsTag,
    ) -> None:
        """Record cost metrics for a Pub/Sub publish batch.

        Mirrors Java ``PubSubCostTracker.trackPublish`` (lines 110-134).

        Maps ``message_count`` → ``billed_messages_count`` and
        ``total_bytes`` → ``billed_bytes_written``. USD estimated from
        ``total_bytes`` (throughput drives the bill, not message count).

        Formula (mirrors Java ``bytesToUsd``, lines 182-186)::

            estimated_cost_usd = total_bytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB

        Zero or negative inputs log WARN and record zero; sink called once.

        :param message_count: Number of messages published.
        :param total_bytes:   Total payload bytes published.
        :param run_id:        Pipeline run identifier.
        :param tag:           FinOps attribution tag.
        :raises TypeError: if run_id or tag is None.
        """
        if run_id is None:
            raise TypeError("run_id must not be None")
        if tag is None:
            raise TypeError("tag must not be None")

        if message_count <= 0:
            logger.warning(
                "PubSubCostTracker.track_publish: message_count=%d for run_id=%s "
                "— recording zero messages", message_count, run_id,
            )
        if total_bytes <= 0:
            logger.warning(
                "PubSubCostTracker.track_publish: total_bytes=%d for run_id=%s "
                "— recording zero cost", total_bytes, run_id,
            )

        messages = max(0, message_count)
        billed_bytes = max(0, total_bytes)
        cost_usd = _bytes_to_usd(billed_bytes)

        metrics = CostMetrics(
            run_id=run_id,
            billed_messages_count=messages,
            billed_bytes_written=billed_bytes,
            estimated_cost_usd=cost_usd,
        )
        self._sink.record(metrics, tag)

    def track_subscribe(
        self,
        message_count: int,
        total_bytes: int,
        run_id: str,
        tag: FinOpsTag,
    ) -> None:
        """Record cost metrics for a Pub/Sub subscription pull/push batch.

        Mirrors Java ``PubSubCostTracker.trackSubscribe`` (lines 153-177).
        Pub/Sub charges both publisher and subscriber throughput, so the
        same formula and rate apply.

        :param message_count: Number of messages received.
        :param total_bytes:   Total payload bytes received.
        :param run_id:        Pipeline run identifier.
        :param tag:           FinOps attribution tag.
        :raises TypeError: if run_id or tag is None.
        """
        if run_id is None:
            raise TypeError("run_id must not be None")
        if tag is None:
            raise TypeError("tag must not be None")

        if message_count <= 0:
            logger.warning(
                "PubSubCostTracker.track_subscribe: message_count=%d for run_id=%s "
                "— recording zero messages", message_count, run_id,
            )
        if total_bytes <= 0:
            logger.warning(
                "PubSubCostTracker.track_subscribe: total_bytes=%d for run_id=%s "
                "— recording zero cost", total_bytes, run_id,
            )

        messages = max(0, message_count)
        billed_bytes = max(0, total_bytes)
        cost_usd = _bytes_to_usd(billed_bytes)

        metrics = CostMetrics(
            run_id=run_id,
            billed_messages_count=messages,
            billed_bytes_written=billed_bytes,
            estimated_cost_usd=cost_usd,
        )
        self._sink.record(metrics, tag)


# ---------------------------------------------------------------------------
# Module-level formula helper (used by tests to verify the unit chain)
# ---------------------------------------------------------------------------

def bytes_to_usd(bytes_count: int) -> float:
    """Convert bytes to USD using THROUGHPUT_COST_USD_PER_TIB.

    Mirrors Java ``PubSubCostTracker.bytesToUsd`` (lines 182-186)::

        return (double) bytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;

    Zero or negative input returns 0.0 (mirrors Java guard on line 183).
    """
    if bytes_count <= 0:
        return 0.0
    return bytes_count / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB


# Internal alias.
_bytes_to_usd = bytes_to_usd

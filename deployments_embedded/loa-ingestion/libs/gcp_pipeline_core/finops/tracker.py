"""GCP service cost estimation and tracking."""

import logging
from typing import Optional, List
from google.cloud import bigquery, storage, pubsub_v1
from .models import CostMetrics

logger = logging.getLogger(__name__)

# Constants for estimation (approximate pricing as of early 2024)
BQ_COST_PER_TIB = 6.25
BQ_COST_PER_BYTE = BQ_COST_PER_TIB / (1024 ** 4)

GCS_STORAGE_COST_PER_GB_MONTH = 0.02  # Standard storage
GCS_PUT_COPY_POST_COST_PER_10K = 0.05
GCS_GET_SELECT_COST_PER_10K = 0.004

PUBSUB_COST_PER_TIB_THROUGHPUT = 40.0
PUBSUB_COST_PER_BYTE = PUBSUB_COST_PER_TIB_THROUGHPUT / (1024 ** 4)


class BigQueryCostTracker:
    """Tracks and estimates costs for BigQuery operations."""

    @staticmethod
    def estimate_query_cost(query_job: bigquery.QueryJob) -> CostMetrics:
        """
        Estimate cost from a completed BigQuery query job.

        Args:
            query_job: The completed BigQuery QueryJob object.

        Returns:
            CostMetrics object containing estimated USD cost and billed bytes scanned.
        """
        if not query_job.total_bytes_billed:
            logger.warning("Query job %s has no billed bytes info.", query_job.job_id)
            return CostMetrics(run_id=query_job.labels.get("run_id", "unknown"))

        bytes_billed = query_job.total_bytes_billed
        estimated_cost = bytes_billed * BQ_COST_PER_BYTE

        return CostMetrics(
            run_id=query_job.labels.get("run_id", "unknown"),
            estimated_cost_usd=estimated_cost,
            billed_bytes_scanned=bytes_billed,
            slot_millis=query_job.slot_millis or 0,
            labels=query_job.labels or {}
        )

    @staticmethod
    def estimate_load_cost(load_job: bigquery.LoadJob) -> CostMetrics:
        """
        Estimate cost from a completed BigQuery load job.

        Note:
            Load jobs are generally free in BigQuery, but we track bytes written
            for storage FinOps and throughput monitoring.

        Args:
            load_job: The completed BigQuery LoadJob object.

        Returns:
            CostMetrics object containing billed bytes written.
        """
        return CostMetrics(
            run_id=load_job.labels.get("run_id", "unknown"),
            billed_bytes_written=load_job.output_bytes or 0,
            labels=load_job.labels or {}
        )


class CloudStorageCostTracker:
    """Tracks and estimates costs for GCS operations."""

    @staticmethod
    def estimate_upload_cost(blob: storage.Blob, run_id: str = "unknown") -> CostMetrics:
        """
        Estimate cost of uploading a blob.

        Args:
            blob: The GCS Blob object that was uploaded.
            run_id: Unique identifier for the pipeline run.

        Returns:
            CostMetrics object containing estimated USD cost and billed bytes written.
        """
        size_bytes = blob.size or 0
        # Minimal estimation: focus on storage and API calls if possible
        # Here we just track bytes written for now.
        return CostMetrics(
            run_id=run_id,
            billed_bytes_written=size_bytes,
            estimated_cost_usd=(1 / 10000) * GCS_PUT_COPY_POST_COST_PER_10K
        )

    @staticmethod
    def estimate_storage_cost(bucket: storage.Bucket, run_id: str = "unknown") -> CostMetrics:
        """
        Estimate monthly storage cost for a bucket.

        Args:
            bucket: The GCS Bucket object to analyze.
            run_id: Unique identifier for the pipeline run.

        Returns:
            CostMetrics object containing estimated monthly USD cost and billed bytes stored.
        """
        # This is a very rough estimation as it depends on how long data stays
        total_bytes = sum(b.size for b in bucket.list_blobs())
        estimated_monthly_cost = (total_bytes / (1024 ** 3)) * GCS_STORAGE_COST_PER_GB_MONTH
        return CostMetrics(
            run_id=run_id,
            billed_bytes_stored=total_bytes,
            estimated_cost_usd=estimated_monthly_cost
        )


class PubSubCostTracker:
    """Tracks and estimates costs for Pub/Sub operations."""

    @staticmethod
    def estimate_publish_cost(message_size_bytes: int, run_id: str = "unknown") -> CostMetrics:
        """
        Estimate cost of publishing a message.

        Args:
            message_size_bytes: Size of the message payload in bytes.
            run_id: Unique identifier for the pipeline run.

        Returns:
            CostMetrics object containing estimated USD cost and billed messages count.
        """
        # Pub/Sub charges for throughput. Minimum 1KB per message.
        billed_bytes = max(message_size_bytes, 1024)
        estimated_cost = billed_bytes * PUBSUB_COST_PER_BYTE
        return CostMetrics(
            run_id=run_id,
            billed_bytes_written=billed_bytes,
            billed_messages_count=1,
            estimated_cost_usd=estimated_cost
        )

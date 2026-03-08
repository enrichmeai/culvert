"""FinOps utilities for GCP data pipelines."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class CostMetrics:
    """
    Cost-related metrics for a pipeline run.

    Attributes:
        run_id: Unique identifier for the pipeline run.
        estimated_cost_usd: Estimated cost in USD.
        billed_bytes_scanned: Number of bytes scanned (e.g., BigQuery queries).
        billed_bytes_written: Number of bytes written (e.g., BigQuery loads, GCS uploads).
        billed_bytes_stored: Number of bytes stored (e.g., GCS storage).
        billed_messages_count: Number of Pub/Sub messages processed.
        slot_millis: BigQuery slot usage in milliseconds.
        compute_units: Normalized compute units (e.g., Dataflow vCPU-seconds).
        labels: Resource labels associated with the costs.
        timestamp: Time when metrics were recorded.
    """
    run_id: str
    estimated_cost_usd: float = 0.0
    billed_bytes_scanned: int = 0
    billed_bytes_written: int = 0
    billed_bytes_stored: int = 0
    billed_messages_count: int = 0
    slot_millis: int = 0
    compute_units: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def cost_per_record(self) -> float:
        """
        Calculate cost per record if applicable.

        Note:
            This is a placeholder and currently returns 0.0.
            Requires total_records which is not part of this model.

        Returns:
            Calculated cost per record in USD.
        """
        return 0.0

"""CostMetrics dataclass — the unit of cost emission.

The fields cover BigQuery slot-millis, scanned/written bytes, GCS storage
bytes, and Pub/Sub message counts — but the dataclass itself is
generic. AWS Redshift slot equivalents (or Azure DWUs) populate the same
fields; the cloud-specific cost-tracker decides how each metric maps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict


def _utc_now() -> datetime:
    """Timezone-aware UTC timestamp. Replaces deprecated `datetime.utcnow()`."""
    return datetime.now(timezone.utc)


@dataclass
class CostMetrics:
    """Cost metrics for a single operation (a query, a load, an upload).

    All fields default to zero so the same dataclass can be used for
    operations that don't fill every dimension (a GCS upload populates
    `billed_bytes_written` but not `slot_millis`).
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
    timestamp: datetime = field(default_factory=_utc_now)

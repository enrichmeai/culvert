"""
Quarantine management for malformed records.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from .types import MalformedRecord, QuarantineLevel

logger = logging.getLogger(__name__)


class QuarantineManager:
    """Manages quarantine of malformed records."""

    def __init__(self):
        """Initialize the quarantine manager."""
        self.quarantine_audit_trail: List[Dict[str, Any]] = []

    def quarantine_malformed(self, record: MalformedRecord,
                            run_id: Optional[str] = None):
        """
        Quarantine malformed record.

        Args:
            record: The malformed record to quarantine
            run_id: Pipeline run ID for audit trail
        """
        record.mark_for_quarantine()

        self.quarantine_audit_trail.append({
            "action": "QUARANTINE",
            "record_id": record.record_id,
            "entity_type": record.entity_type,
            "reasons": record.reasons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id
        })

        logger.info("Record quarantined: %s", record.record_id)

    def _filter_by_quarantine_level(
        self,
        records: List[MalformedRecord],
        level: QuarantineLevel
    ) -> List[MalformedRecord]:
        """Filter records by quarantine level."""
        return [
            m for m in records
            if m.quarantine_level == level
        ]

    def get_quarantined_records(
        self,
        records: List[MalformedRecord]
    ) -> List[MalformedRecord]:
        """Get all quarantined records from a list."""
        return self._filter_by_quarantine_level(
            records, QuarantineLevel.QUARANTINE
        )

    def get_review_only_records(
        self,
        records: List[MalformedRecord]
    ) -> List[MalformedRecord]:
        """Get all review-only records from a list."""
        return self._filter_by_quarantine_level(
            records, QuarantineLevel.REVIEW_ONLY
        )

    def get_approved_for_deletion_records(
        self,
        records: List[MalformedRecord]
    ) -> List[MalformedRecord]:
        """Get all records approved for deletion from a list."""
        return self._filter_by_quarantine_level(
            records, QuarantineLevel.DELETE_APPROVED
        )

    def get_deleted_records(
        self,
        records: List[MalformedRecord]
    ) -> List[MalformedRecord]:
        """Get all deleted records from a list."""
        return self._filter_by_quarantine_level(
            records, QuarantineLevel.DELETED
        )

    def get_quarantine_audit_trail(self) -> List[Dict[str, Any]]:
        """Get quarantine audit trail."""
        return self.quarantine_audit_trail.copy()

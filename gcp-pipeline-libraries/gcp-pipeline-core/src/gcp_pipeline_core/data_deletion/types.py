"""
Data deletion types, enums, and data structures.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class MalformationReason(Enum):
    """Reasons for data malformation."""
    INCOMPLETE_RECORD = "incomplete_record"
    INVALID_FORMAT = "invalid_format"
    CORRUPTED_FILE = "corrupted_file"
    ENCODING_ERROR = "encoding_error"
    SCHEMA_MISMATCH = "schema_mismatch"
    DUPLICATE_RECORD = "duplicate_record"
    INVALID_DATE = "invalid_date"
    INVALID_NUMERIC = "invalid_numeric"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    UNKNOWN = "unknown"


class QuarantineLevel(Enum):
    """Severity levels for quarantine."""
    REVIEW_ONLY = "review_only"  # Mark for review, don't delete
    QUARANTINE = "quarantine"  # Move to quarantine bucket
    DELETE_APPROVED = "delete_approved"  # Ready for deletion
    DELETED = "deleted"  # Successfully deleted


class MalformedRecord:
    """Represents a malformed/problematic record."""

    def __init__(
            self,
            record_id: str,
            entity_type: str,
            original_data: Dict[str, Any],
            reasons: List[str],
            severity: str = "MEDIUM",
            first_detected: Optional[datetime] = None
    ):
        """
        Initialize malformed record.

        Args:
            record_id: Unique identifier for the record
            entity_type: Entity type (APPLICATION, CUSTOMER, etc.)
            original_data: Original record data
            reasons: List of reasons for malformation
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            first_detected: When first detected
        """
        self.record_id = record_id
        self.entity_type = entity_type
        self.original_data = original_data
        self.reasons = reasons
        self.severity = severity
        self.first_detected = first_detected or datetime.now(tz=timezone.utc)
        self.quarantine_level = QuarantineLevel.REVIEW_ONLY
        self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum of original data."""
        data_str = str(sorted(self.original_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def mark_for_quarantine(self):
        """Mark record for quarantine."""
        self.quarantine_level = QuarantineLevel.QUARANTINE

    def approve_for_deletion(self):
        """Approve record for deletion."""
        self.quarantine_level = QuarantineLevel.DELETE_APPROVED

    def mark_deleted(self):
        """Mark as deleted."""
        self.quarantine_level = QuarantineLevel.DELETED

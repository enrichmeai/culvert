"""
Malformation detection logic for identifying problematic records.
"""

import logging
from typing import Dict, List, Any
from .types import MalformedRecord

logger = logging.getLogger(__name__)


class MalformationDetector:
    """Detects and registers malformed records."""

    def __init__(self):
        """Initialize the detector."""
        self.malformed_records: List[MalformedRecord] = []

    def detect_malformed_record(
        self,
        record_id: str,
        entity_type: str,
        data: Dict[str, Any],
        validation_errors: List[str],
        severity: str = "MEDIUM"
    ) -> MalformedRecord:
        """
        Detect and register malformed record.

        Args:
            record_id: Unique identifier for the record
            entity_type: Type of entity
            data: Original record data
            validation_errors: List of validation errors
            severity: Severity level

        Returns:
            MalformedRecord instance
        """
        malformed = MalformedRecord(
            record_id=record_id,
            entity_type=entity_type,
            original_data=data,
            reasons=validation_errors,
            severity=severity
        )

        self.malformed_records.append(malformed)

        logger.warning(
            "Malformed record detected: %s - %s",
            record_id, ', '.join(validation_errors)
        )

        return malformed

    def get_malformed_records_by_severity(
        self,
        severity: str
    ) -> List[MalformedRecord]:
        """Get malformed records by severity."""
        return [m for m in self.malformed_records
                if m.severity == severity]

    def get_malformed_records_by_entity(
        self,
        entity_type: str
    ) -> List[MalformedRecord]:
        """Get malformed records by entity type."""
        return [m for m in self.malformed_records
                if m.entity_type == entity_type]

    def get_all_malformed_records(self) -> List[MalformedRecord]:
        """Get all malformed records."""
        return self.malformed_records.copy()


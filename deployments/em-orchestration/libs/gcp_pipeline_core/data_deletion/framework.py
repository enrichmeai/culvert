"""
Data Deletion Framework - High-level orchestration of deletion operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from .types import MalformedRecord, QuarantineLevel
from .detector import MalformationDetector
from .quarantine import QuarantineManager
from .deletion import SafeDataDeletion
from .recovery import RecoveryManager

logger = logging.getLogger(__name__)


def _get_logger() -> logging.Logger:
    """Get the package-level logger for test compatibility."""
    return logger


class DataDeletionFramework:
    """Framework for safe data deletion with audit trail."""

    def __init__(self, pipeline_name: str, run_id: str):
        """
        Initialize framework.

        Args:
            pipeline_name: Name of pipeline
            run_id: Run ID for tracking
        """
        self.pipeline_name = pipeline_name
        self.run_id = run_id

        # Initialize sub-managers
        self.detector = MalformationDetector()
        self.quarantine_manager = QuarantineManager()
        self.deletion_manager = SafeDataDeletion()
        self.recovery_manager = RecoveryManager()

        # Keep copies for backward compatibility
        self.malformed_records: List[MalformedRecord] = []
        self.deletion_audit_trail: List[Dict[str, Any]] = []
        self.recovery_points: Dict[str, Dict[str, Any]] = {}

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
        malformed = self.detector.detect_malformed_record(
            record_id=record_id,
            entity_type=entity_type,
            data=data,
            validation_errors=validation_errors,
            severity=severity
        )

        # Keep in local list for backward compatibility
        self.malformed_records.append(malformed)

        return malformed

    def create_recovery_point(
            self,
            checkpoint_name: str,
            state: Dict[str, Any]
    ) -> None:
        """
        Create recovery point before deletion.

        Args:
            checkpoint_name: Name of the checkpoint
            state: Current state to save
        """
        recovery_point = self.recovery_manager.create_recovery_point(
            checkpoint_name=checkpoint_name,
            state=state,
            malformed_records=self.detector.malformed_records
        )

        # Keep in local dict for backward compatibility
        self.recovery_points[checkpoint_name] = {
            "timestamp": recovery_point.timestamp,
            "state": recovery_point.state,
            "malformed_records": recovery_point.malformed_records
        }

        _get_logger().info("Recovery point created: %s", checkpoint_name)

    def quarantine_malformed(self, record: MalformedRecord) -> None:
        """
        Quarantine malformed record.

        Args:
            record: The record to quarantine
        """
        self.quarantine_manager.quarantine_malformed(
            record, run_id=self.run_id)

        # Add to audit trail
        self.deletion_audit_trail.append({
            "action": "QUARANTINE",
            "record_id": record.record_id,
            "entity_type": record.entity_type,
            "reasons": record.reasons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        })

        _get_logger().info("Record quarantined: %s", record.record_id)

    def request_deletion_approval(
            self,
            record: MalformedRecord
    ) -> Dict[str, Any]:
        """
        Request approval for deletion.

        Args:
            record: The record to request deletion for

        Returns:
            Approval request details
        """
        approval_request = self.deletion_manager.request_deletion_approval(
            record)

        # Add to audit trail
        self.deletion_audit_trail.append({
            "action": "DELETION_REQUESTED",
            "record_id": record.record_id,
            "request_id": approval_request["request_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        })

        _get_logger().info("Deletion approval requested for: %s",
                           record.record_id)

        return approval_request

    def approve_deletion(self, record: MalformedRecord, approved_by: str) -> None:
        """
        Approve deletion of record.

        Args:
            record: The record to approve
            approved_by: User/service approving
        """
        self.deletion_manager.approve_deletion(
            record, approved_by, run_id=self.run_id)

        # Add to audit trail
        self.deletion_audit_trail.append({
            "action": "DELETION_APPROVED",
            "record_id": record.record_id,
            "approved_by": approved_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        })

        _get_logger().info("Deletion approved for: %s by %s",
                           record.record_id, approved_by)

    def delete_record(self, record: MalformedRecord) -> bool:
        """
        Delete approved malformed record.

        Args:
            record: The record to delete

        Returns:
            True if successful, False otherwise
        """
        log = _get_logger()

        if record.quarantine_level != QuarantineLevel.DELETE_APPROVED:
            log.error(
                "Cannot delete record %s - not approved for deletion",
                record.record_id
            )
            return False

        try:
            # Mark as deleted
            record.mark_deleted()

            self.deletion_audit_trail.append({
                "action": "DELETED",
                "record_id": record.record_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id
            })

            log.info("Record deleted: %s", record.record_id)
            return True

        except (ValueError, RuntimeError) as exc:
            log.error("Failed to delete record %s: %s",
                      record.record_id, str(exc))
            return False

    def restore_from_recovery_point(
            self,
            checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore from recovery point.

        Args:
            checkpoint_name: Name of checkpoint to restore

        Returns:
            Restored state or None if not found
        """
        restored = self.recovery_manager.restore_from_recovery_point(
            checkpoint_name)

        if restored:
            # Add to audit trail
            self.deletion_audit_trail.append({
                "action": "RESTORED",
                "checkpoint": checkpoint_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id
            })

        return restored

    def _calculate_statistics(self) -> Dict[str, int]:
        """Calculate statistics for malformed records by quarantine level."""
        records = self.detector.malformed_records
        return {
            "total_malformed": len(records),
            "review_only": sum(
                1 for m in records
                if m.quarantine_level == QuarantineLevel.REVIEW_ONLY
            ),
            "quarantined": sum(
                1 for m in records
                if m.quarantine_level == QuarantineLevel.QUARANTINE
            ),
            "approved_for_deletion": sum(
                1 for m in records
                if m.quarantine_level == QuarantineLevel.DELETE_APPROVED
            ),
            "deleted": sum(
                1 for m in records
                if m.quarantine_level == QuarantineLevel.DELETED
            )
        }

    def get_deletion_report(self) -> Dict[str, Any]:
        """
        Get deletion and quarantine report.

        Returns:
            Report dictionary
        """
        report = {
            "pipeline": self.pipeline_name,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": self._calculate_statistics(),
            "audit_trail_length": len(self.deletion_audit_trail),
            "recovery_points": self.recovery_manager.list_recovery_points()
        }

        return report

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get full audit trail."""
        return self.deletion_audit_trail.copy()

    def get_malformed_records_by_severity(
            self,
            severity: str
    ) -> List[MalformedRecord]:
        """Get malformed records by severity."""
        return self.detector.get_malformed_records_by_severity(severity)

    def get_malformed_records_by_entity(
            self,
            entity_type: str
    ) -> List[MalformedRecord]:
        """Get malformed records by entity type."""
        return self.detector.get_malformed_records_by_entity(entity_type)

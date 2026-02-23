"""
Safe data deletion with audit trail and approval workflows.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from ..utilities.logging import get_logger
from .types import MalformedRecord, QuarantineLevel

logger = get_logger(__name__)


class DeletionPolicy:
    """Policy for safe deletion of records."""

    def __init__(self, require_approval: bool = True, max_batch_size: int = 1000):
        """
        Initialize deletion policy.

        Args:
            require_approval: Whether deletion requires approval
            max_batch_size: Maximum records to delete in one batch
        """
        self.require_approval = require_approval
        self.max_batch_size = max_batch_size


class SafeDataDeletion:
    """Manages safe deletion of records with full audit trail."""

    def __init__(self, deletion_policy: Optional[DeletionPolicy] = None):
        """
        Initialize safe deletion manager.

        Args:
            deletion_policy: Policy governing deletions
        """
        self.policy = deletion_policy or DeletionPolicy()
        self.deletion_audit_trail: List[Dict[str, Any]] = []

    def request_deletion_approval(
        self,
        record: MalformedRecord
    ) -> Dict[str, Any]:
        """
        Request approval for deletion.

        Args:
            record: The record to delete

        Returns:
            Approval request details
        """
        now = datetime.now(timezone.utc)
        approval_request = {
            "request_id": f"DELETE_REQ_{record.record_id}_{now.timestamp()}",
            "record_id": record.record_id,
            "entity_type": record.entity_type,
            "original_data": record.original_data,
            "reasons": record.reasons,
            "severity": record.severity,
            "checksum": record.checksum,
            "first_detected": record.first_detected.isoformat(),
            "status": "PENDING_APPROVAL",
            "created_at": now.isoformat()
        }

        self.deletion_audit_trail.append({
            "action": "DELETION_REQUESTED",
            "record_id": record.record_id,
            "request_id": approval_request["request_id"],
            "timestamp": now.isoformat()
        })

        logger.info("Deletion approval requested for record", record_id=record.record_id)

        return approval_request

    def approve_deletion(
        self,
        record: MalformedRecord,
        approved_by: str,
        run_id: Optional[str] = None
    ):
        """
        Approve deletion of record.

        Args:
            record: The record to approve for deletion
            approved_by: User/service approving deletion
            run_id: Pipeline run ID
        """
        record.approve_for_deletion()

        self.deletion_audit_trail.append({
            "action": "DELETION_APPROVED",
            "record_id": record.record_id,
            "approved_by": approved_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id
        })

        logger.info("Deletion approved for record", record_id=record.record_id, approved_by=approved_by)
    def delete_record(
        self,
        record: MalformedRecord,
        run_id: Optional[str] = None
    ) -> bool:
        """
        Delete approved malformed record.

        Args:
            record: The record to delete
            run_id: Pipeline run ID

        Returns:
            True if deletion succeeded, False otherwise
        """
        if record.quarantine_level != QuarantineLevel.DELETE_APPROVED:
            logger.error(
                "Cannot delete record - not approved for deletion",
                record_id=record.record_id
            )
            return False

        try:
            # Mark as deleted
            record.mark_deleted()

            self.deletion_audit_trail.append({
                "action": "DELETED",
                "record_id": record.record_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id
            })

            logger.info("Record deleted", record_id=record.record_id)
            return True

        except Exception as exc:
            logger.error("Failed to delete record",
                        record_id=record.record_id, error=str(exc), exc_info=True)
            return False

    def delete_batch(
        self,
        records: List[MalformedRecord],
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete a batch of approved records.

        Args:
            records: List of records to delete
            run_id: Pipeline run ID

        Returns:
            Summary of deletion results
        """
        results = {
            "total": len(records),
            "deleted": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        # Apply batch size limit from policy
        records_to_process = records[:self.policy.max_batch_size]
        results["skipped"] = len(records) - len(records_to_process)

        for record in records_to_process:
            try:
                if self.delete_record(record, run_id=run_id):
                    results["deleted"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "record_id": record.record_id,
                        "error": "Record not approved for deletion"
                    })
            except Exception as exc:
                results["failed"] += 1
                results["errors"].append({
                    "record_id": record.record_id,
                    "error": str(exc)
                })

        logger.info(
            "Batch deletion completed",
            deleted=results["deleted"], failed=results["failed"], skipped=results["skipped"]
        )
        return results


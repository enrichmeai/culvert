"""Tests for safe data deletion manager."""

import pytest
from gcp_pipeline_core.data_deletion.deletion import SafeDataDeletion, DeletionPolicy
from gcp_pipeline_core.data_deletion.types import MalformedRecord, QuarantineLevel

class TestSafeDataDeletion:
    """Tests for SafeDataDeletion class."""

    def test_request_deletion_approval(self):
        """Test requesting deletion approval."""
        manager = SafeDataDeletion()
        record = MalformedRecord("rec-1", "CUSTOMER", {"data": "test"}, ["reason"])
        
        request = manager.request_deletion_approval(record)
        
        assert request["record_id"] == "rec-1"
        assert request["status"] == "PENDING_APPROVAL"
        assert len(manager.deletion_audit_trail) == 1
        assert manager.deletion_audit_trail[0]["action"] == "DELETION_REQUESTED"

    def test_approve_deletion(self):
        """Test approving a deletion request."""
        manager = SafeDataDeletion()
        record = MalformedRecord("rec-1", "CUSTOMER", {}, [])
        
        manager.approve_deletion(record, approved_by="admin-user")
        
        assert record.quarantine_level == QuarantineLevel.DELETE_APPROVED
        assert any(entry["action"] == "DELETION_APPROVED" for entry in manager.deletion_audit_trail)

    def test_delete_record_fails_without_approval(self):
        """Test that deletion fails if not approved."""
        manager = SafeDataDeletion()
        record = MalformedRecord("rec-1", "CUSTOMER", {}, [])
        
        success = manager.delete_record(record)
        assert success is False
        assert record.quarantine_level == QuarantineLevel.REVIEW_ONLY

    def test_delete_record_success_after_approval(self):
        """Test successful deletion after approval."""
        manager = SafeDataDeletion()
        record = MalformedRecord("rec-1", "CUSTOMER", {}, [])
        
        manager.approve_deletion(record, "admin")
        success = manager.delete_record(record)
        
        assert success is True
        assert record.quarantine_level == QuarantineLevel.DELETED
        assert any(entry["action"] == "DELETED" for entry in manager.deletion_audit_trail)

    def test_delete_batch(self):
        """Test batch deletion logic."""
        manager = SafeDataDeletion(DeletionPolicy(max_batch_size=2))
        
        rec1 = MalformedRecord("1", "T", {}, [])
        rec2 = MalformedRecord("2", "T", {}, [])
        rec3 = MalformedRecord("3", "T", {}, [])
        
        manager.approve_deletion(rec1, "admin")
        manager.approve_deletion(rec2, "admin")
        manager.approve_deletion(rec3, "admin")
        
        results = manager.delete_batch([rec1, rec2, rec3])
        
        assert results["total"] == 3
        assert results["deleted"] == 2
        assert results["skipped"] == 1
        assert rec1.quarantine_level == QuarantineLevel.DELETED
        assert rec2.quarantine_level == QuarantineLevel.DELETED
        assert rec3.quarantine_level == QuarantineLevel.DELETE_APPROVED # Still only approved, not deleted

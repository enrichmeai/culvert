"""Tests for data deletion types."""

from datetime import datetime
from gcp_pipeline_core.data_deletion.types import MalformedRecord, QuarantineLevel

class TestMalformedRecord:
    """Tests for MalformedRecord class."""

    def test_record_initialization(self):
        """Test record initialization."""
        data = {"id": "1", "name": "test"}
        record = MalformedRecord(
            record_id="rec-123",
            entity_type="CUSTOMER",
            original_data=data,
            reasons=["missing_email"]
        )
        
        assert record.record_id == "rec-123"
        assert record.entity_type == "CUSTOMER"
        assert record.original_data == data
        assert record.reasons == ["missing_email"]
        assert record.quarantine_level == QuarantineLevel.REVIEW_ONLY
        assert record.checksum is not None

    def test_quarantine_lifecycle(self):
        """Test record lifecycle through quarantine levels."""
        record = MalformedRecord("1", "T", {}, [])
        
        record.mark_for_quarantine()
        assert record.quarantine_level == QuarantineLevel.QUARANTINE
        
        record.approve_for_deletion()
        assert record.quarantine_level == QuarantineLevel.DELETE_APPROVED
        
        record.mark_deleted()
        assert record.quarantine_level == QuarantineLevel.DELETED

    def test_checksum_consistency(self):
        """Test that same data produces same checksum."""
        data = {"a": 1, "b": 2}
        record1 = MalformedRecord("1", "T", data, [])
        record2 = MalformedRecord("2", "T", {"b": 2, "a": 1}, [])
        
        assert record1.checksum == record2.checksum

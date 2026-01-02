"""
Audit Framework Unit Tests

Comprehensive tests for audit trail management, duplicate detection,
reconciliation, and data lineage tracking.

Tests: AuditTrail, DuplicateDetector, ReconciliationEngine
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any
import hashlib

from gdw_data_core.core.audit import (
    AuditTrail,
    DuplicateDetector,
    ReconciliationEngine,
    AuditEntry,
    ReconciliationReport
)


class TestAuditEntry:
    """Test suite for AuditEntry."""

    def test_audit_entry_creation(self):
        """Test creating audit entry."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            run_id="run_001",
            entity_type="APPLICATION",
            status="LOADED",
            message="Test message",
            context={}
        )

        assert entry.run_id == "run_001"
        assert entry.entity_type == "APPLICATION"
        assert entry.status == "LOADED"
        assert entry.timestamp is not None

    def test_audit_entry_with_context(self):
        """Test audit entry with context data."""
        context = {
            "source_file": "gs://bucket/app.csv",
            "batch_id": "BATCH001",
            "row_number": 42
        }

        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            run_id="run_001",
            entity_type="APPLICATION",
            status="LOADED",
            message="Test message",
            context=context
        )

        assert entry.context == context
        assert entry.context["source_file"] == "gs://bucket/app.csv"

    def test_audit_entry_with_error(self):
        """Test audit entry with error details."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            run_id="run_001",
            entity_type="APPLICATION",
            status="FAILED",
            message="Invalid SSN format",
            context={"field": "ssn", "value": "INVALID"}
        )

        assert entry.status == "FAILED"
        assert entry.message == "Invalid SSN format"
        assert entry.context["field"] == "ssn"


class TestAuditTrail:
    """Test suite for AuditTrail."""

    @pytest.fixture
    def audit_trail(self):
        """Create AuditTrail for testing."""
        return AuditTrail(
            pipeline_name="test_pipeline",
            run_id="test_run_001",
            entity_type="test_entity"
        )

    def test_audit_trail_initialization(self, audit_trail):
        """Test audit trail initialization."""
        assert audit_trail.pipeline_name == "test_pipeline"
        assert audit_trail.run_id == "test_run_001"

    def test_log_entry_success(self, audit_trail):
        """Test logging successful entry."""
        audit_trail.log_entry(
            status="SUCCESS",
            message="Record processed"
        )
        assert audit_trail.get_entry_count() == 1
        assert audit_trail.get_entry_count_by_status("SUCCESS") == 1

    def test_log_entry_failure(self, audit_trail):
        """Test logging failed entry."""
        audit_trail.log_entry(
            status="FAILURE",
            message="Validation failed",
            context={"reason": "Invalid SSN"}
        )
        assert audit_trail.get_entry_count() == 1
        assert audit_trail.get_entry_count_by_status("FAILURE") == 1

    def test_log_multiple_entries(self, audit_trail):
        """Test logging multiple entries."""
        for i in range(10):
            audit_trail.log_entry(
                status="LOADED",
                message=f"Loaded {i}"
            )

        assert audit_trail.get_entry_count() == 10

    def test_get_entries_by_status(self, audit_trail):
        """Test filtering entries by status."""
        audit_trail.log_entry(status="LOADED", message="1")
        audit_trail.log_entry(status="FAILED", message="2")
        audit_trail.log_entry(status="LOADED", message="3")

        loaded_entries = audit_trail.get_entries_by_status("LOADED")

        assert len(loaded_entries) == 2
        assert all(e.status == "LOADED" for e in loaded_entries)

    def test_get_entries_by_entity_type(self, audit_trail):
        """Test filtering entries by entity type."""
        # Using separate AuditTrail instances for different entities is more realistic,
        # but the class can be used to log different things if needed by test
        audit_trail.entity_type = "APPLICATION"
        audit_trail.log_entry(status="LOADED", message="1")
        
        audit_trail.entity_type = "CUSTOMER"
        audit_trail.log_entry(status="LOADED", message="2")
        
        audit_trail.entity_type = "APPLICATION"
        audit_trail.log_entry(status="LOADED", message="3")

        app_entries = audit_trail.get_entries_by_entity_type("APPLICATION")

        assert len(app_entries) == 2
        assert all(e.entity_type == "APPLICATION" for e in app_entries)

    def test_get_entry_count(self, audit_trail):
        """Test getting entry count."""
        for i in range(5):
            audit_trail.log_entry(status="LOADED", message=f"REC{i}")

        assert audit_trail.get_entry_count() == 5

    def test_get_entry_count_by_status(self, audit_trail):
        """Test getting count by status."""
        for i in range(3):
            audit_trail.log_entry(status="LOADED", message=f"REC{i}")
        for i in range(2):
            audit_trail.log_entry(status="FAILED", message=f"ERR{i}")

        loaded_count = audit_trail.get_entry_count_by_status("LOADED")
        failed_count = audit_trail.get_entry_count_by_status("FAILED")

        assert loaded_count == 3
        assert failed_count == 2

    def test_audit_entry_timestamps(self, audit_trail):
        """Test that timestamps are recorded correctly."""
        before_time = datetime.utcnow()
        audit_trail.log_entry(status="LOADED", message="REC001")
        after_time = datetime.utcnow()

        entries = audit_trail.get_entries()
        assert before_time <= entries[0].timestamp <= after_time


class TestDuplicateDetector:
    """Test suite for DuplicateDetector."""

    @pytest.fixture
    def detector(self):
        """Create DuplicateDetector for testing."""
        return DuplicateDetector()

    def test_detect_exact_duplicate(self, detector):
        """Test detecting exact duplicate records."""
        record1 = {"id": "REC001", "name": "John", "ssn": "123-45-6789"}
        record2 = {"id": "REC001", "name": "John", "ssn": "123-45-6789"}

        is_duplicate = detector.is_duplicate(record1, record2, key_fields=["id"])

        assert is_duplicate is True

    def test_detect_no_duplicate(self, detector):
        """Test no duplicate detection for different records."""
        record1 = {"id": "REC001", "name": "John", "ssn": "123-45-6789"}
        record2 = {"id": "REC002", "name": "Jane", "ssn": "987-65-4321"}

        is_duplicate = detector.is_duplicate(record1, record2, key_fields=["id"])

        assert is_duplicate is False

    def test_detect_partial_duplicate(self, detector):
        """Test detecting partial duplicates."""
        records = [
            {"id": "REC001", "name": "John", "ssn": "123-45-6789"},
            {"id": "REC001", "name": "John", "ssn": "123-45-6789"},
            {"id": "REC002", "name": "Jane", "ssn": "987-65-4321"}
        ]

        duplicates = detector.find_duplicates(records, key_fields=["id"])

        assert len(duplicates) > 0

    def test_detect_duplicates_in_batch(self, detector):
        """Test detecting duplicates in a batch."""
        records = [
            {"id": "APP001", "name": "John"},
            {"id": "APP002", "name": "Jane"},
            {"id": "APP001", "name": "John"},  # Duplicate of first
            {"id": "APP003", "name": "Bob"}
        ]

        duplicates = detector.find_duplicates(records, key_fields=["id", "name"])

        assert len(duplicates) >= 1  # At least one duplicate found

    def test_duplicate_detection_with_custom_logic(self, detector):
        """Test duplicate detection with custom comparison logic."""
        record1 = {"id": "REC001", "ssn": "123-45-6789"}
        record2 = {"id": "REC001", "ssn": "123-45-6789"}

        # Custom: compare by SSN only
        is_duplicate = detector.is_duplicate(
            record1,
            record2,
            key_fields=["ssn"]
        )

        assert is_duplicate is True


class TestReconciliationEngine:
    """Test suite for ReconciliationEngine."""

    @pytest.fixture
    def engine(self):
        """Create ReconciliationEngine for testing."""
        return ReconciliationEngine(entity_type="test_entity")

    def test_reconcile_matching_records(self, engine):
        """Test reconciling matching source and target records."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=100,
            error_count=0
        )

        assert report['reconciled'] is True
        assert report['missing_count'] == 0

    def test_reconcile_missing_records(self, engine):
        """Test reconciliation with missing records."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=95,
            error_count=0
        )

        assert report['reconciled'] is False
        assert report['missing_count'] == 5

    def test_reconcile_extra_records(self, engine):
        """Test reconciliation with extra records in target."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=105,
            error_count=0
        )

        # missing_count would be -5
        assert report['missing_count'] == -5

    def test_reconcile_value_differences(self, engine):
        """Test reconciliation detecting value differences."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=90,
            error_count=10
        )

        assert report['reconciled'] is True
        assert report['total_processed'] == 100

    def test_reconciliation_summary(self, engine):
        """Test getting reconciliation summary."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=95,
            error_count=0
        )

        assert report['source_count'] == 100
        assert report['destination_count'] == 95
        assert report['missing_count'] == 5

    def test_reconciliation_with_percentage_calculation(self, engine):
        """Test reconciliation percentage calculations."""
        report = engine.reconcile_counts(
            source_count=100,
            destination_count=90,
            error_count=0
        )

        # Should be able to calculate match percentage
        assert report['success_rate'] == 90.0


class TestAuditIntegration:
    """Integration tests for audit functionality."""

    def test_full_audit_workflow(self):
        """Test complete audit workflow."""
        audit_trail = AuditTrail("pipeline", "run_001", "APPLICATION")
        detector = DuplicateDetector()
        reconciler = ReconciliationEngine(entity_type="APPLICATION")

        # Log records
        records = [
            {"id": "REC001", "name": "John", "status": "valid"},
            {"id": "REC002", "name": "Jane", "status": "valid"},
            {"id": "REC001", "name": "John", "status": "valid"},  # Duplicate
            {"id": "REC003", "name": "Bob", "status": "valid"}
        ]

        for record in records:
            audit_trail.log_entry(
                status="LOADED",
                message=f"Loaded {record['id']}",
                context={"record_id": record["id"]}
            )

        # Detect duplicates (manual check using seen_records)
        seen = set()
        duplicates = []
        for record in records:
            if detector.is_duplicate(record["id"]):
                duplicates.append(record)
            detector.mark_as_processed(record["id"])

        # Mark duplicates in audit
        for dup in duplicates:
            audit_trail.log_entry(
                status="DUPLICATE",
                message=f"Duplicate found: {dup['id']}",
                context={"record_id": dup["id"]}
            )

        # Verify audit trail
        loaded_entries = audit_trail.get_entries_by_status("LOADED")
        dup_entries = audit_trail.get_entries_by_status("DUPLICATE")

        assert len(loaded_entries) == 4
        assert len(dup_entries) >= 1

    def test_audit_trail_with_reconciliation(self):
        """Test audit trail with reconciliation."""
        audit_trail = AuditTrail("pipeline", "run_001", "APPLICATION")
        reconciler = ReconciliationEngine(entity_type="APPLICATION")

        source_data = [
            {"id": "APP001", "amount": 100000},
            {"id": "APP002", "amount": 200000}
        ]

        # Log source records
        for record in source_data:
            audit_trail.log_entry("LOADED", f"Loaded {record['id']}")

        # Reconcile
        report = reconciler.reconcile_counts(
            source_count=len(source_data),
            destination_count=len(source_data),
            error_count=0
        )

        # Verify audit entries
        entries = audit_trail.entries
        assert len(entries) == len(source_data)
        assert report['destination_count'] == 2


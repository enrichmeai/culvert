import pytest
from datetime import datetime
from unittest.mock import MagicMock
from gdw_data_core.core.audit import AuditTrail, DuplicateDetector, ReconciliationEngine, AuditPublisher

def test_audit_trail_with_publisher():
    mock_publisher = MagicMock(spec=AuditPublisher)
    audit = AuditTrail(
        run_id="test_run",
        pipeline_name="test_pipe",
        entity_type="test_entity",
        publisher=mock_publisher
    )
    audit.record_processing_start(source_file="test.csv")
    audit.increment_counts(valid=10, errors=2)
    audit.record_processing_end(success=True)

    mock_publisher.publish.assert_called_once()

def test_audit_trail():
    audit = AuditTrail(run_id="test_run", pipeline_name="test_pipe", entity_type="test_entity")
    audit.record_processing_start(source_file="test.csv")
    audit.increment_counts(valid=10, errors=2)
    record = audit.record_processing_end(success=True)

    assert record.record_count == 12
    assert record.error_count == 2
    assert record.success is True

def test_duplicate_detector():
    detector = DuplicateDetector()
    assert detector.is_duplicate("rec1") is False
    assert detector.is_duplicate("rec1") is True
    assert detector.is_duplicate("rec2") is False

def test_reconciliation_engine():
    reconciler = ReconciliationEngine(entity_type="test_entity")
    result = reconciler.reconcile_counts(source_count=100, destination_count=95, error_count=5)
    assert result['reconciled'] is True
    assert result['success_rate'] == 95.0

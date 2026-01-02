"""Unit tests for DuplicateDetector and ReconciliationEngine."""

import pytest

from gdw_data_core.core.audit import DuplicateDetector, ReconciliationEngine


class TestDuplicateDetector:
    """Test DuplicateDetector class."""

    def test_duplicate_detection(self):
        """Test duplicate detection."""
        detector = DuplicateDetector()
        assert detector.is_duplicate("rec1") is False
        assert detector.is_duplicate("rec1") is True
        assert detector.is_duplicate("rec2") is False


class TestReconciliationEngine:
    """Test ReconciliationEngine class."""

    def test_reconcile_counts(self):
        """Test count reconciliation."""
        reconciler = ReconciliationEngine(entity_type="test_entity")
        result = reconciler.reconcile_counts(
            source_count=100,
            destination_count=95,
            error_count=5
        )
        assert result['reconciled'] is True
        assert result['success_rate'] == 95.0


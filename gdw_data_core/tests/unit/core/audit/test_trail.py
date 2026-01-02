"""Unit tests for AuditTrail class."""

import pytest
from unittest.mock import MagicMock

from gdw_data_core.core.audit import AuditTrail, AuditPublisher


class TestAuditTrail:
    """Test AuditTrail class."""

    def test_audit_trail_basic(self):
        """Test basic audit trail functionality."""
        audit = AuditTrail(
            run_id="test_run",
            pipeline_name="test_pipe",
            entity_type="test_entity"
        )
        audit.record_processing_start(source_file="test.csv")
        audit.increment_counts(valid=10, errors=2)
        record = audit.record_processing_end(success=True)

        assert record.record_count == 12
        assert record.error_count == 2
        assert record.success is True

    def test_audit_trail_with_publisher(self):
        """Test audit trail with publisher."""
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


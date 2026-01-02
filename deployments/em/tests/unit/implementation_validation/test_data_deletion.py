import pytest
from unittest.mock import Mock, patch
from gdw_data_core.testing import BaseGDWTest
from gdw_data_core.core.data_deletion import DataDeletionFramework, MalformedRecord, QuarantineLevel

class TestDataDeletion(BaseGDWTest):
    def test_data_deletion_framework_init(self):
        dfw = DataDeletionFramework(pipeline_name="test_pipeline", run_id="run_123")
        self.assertEqual(dfw.pipeline_name, "test_pipeline")
        self.assertEqual(dfw.run_id, "run_123")

    def test_detect_malformed_record(self):
        dfw = DataDeletionFramework(pipeline_name="test_pipeline", run_id="run_123")
        record = dfw.detect_malformed_record(
            record_id="REC001",
            entity_type="application",
            data={"id": "REC001", "amount": "invalid"},
            validation_errors=["Invalid amount"]
        )

        self.assertIsInstance(record, MalformedRecord)
        self.assertEqual(record.record_id, "REC001")
        self.assertIn("Invalid amount", record.reasons)

    @patch('gdw_data_core.core.data_deletion.framework._get_logger')
    def test_delete_record(self, mock_get_logger):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        dfw = DataDeletionFramework(pipeline_name="test_pipeline", run_id="run_123")
        record = dfw.detect_malformed_record(
            record_id="REC001",
            entity_type="application",
            data={"id": "REC001"},
            validation_errors=["Error"]
        )

        # Must approve before deletion
        dfw.approve_deletion(record, approved_by="test_user")

        dfw.delete_record(record)
        self.assertEqual(record.quarantine_level, QuarantineLevel.DELETED)
        mock_logger.info.assert_any_call("Record deleted: %s", "REC001")

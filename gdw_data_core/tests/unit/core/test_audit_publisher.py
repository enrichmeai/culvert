import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from gdw_data_core.core.audit.records import AuditRecord
from gdw_data_core.core.audit.publisher import AuditPublisher

class TestAuditPublisher(unittest.TestCase):
    def setUp(self):
        self.project_id = "test-project"
        self.topic_name = "test-audit-topic"
        
        with patch('gdw_data_core.core.audit.publisher.PubSubClient') as mock_client:
            self.publisher = AuditPublisher(self.project_id, self.topic_name)
            self.mock_pubsub = self.publisher.pubsub_client

    def test_prepare_message(self):
        record = AuditRecord(
            run_id="run-123",
            pipeline_name="test-pipeline",
            entity_type="applications",
            source_file="gs://bucket/file.csv",
            record_count=100,
            processed_timestamp=datetime(2025, 1, 1, 12, 0, 0),
            processing_duration_seconds=10.5,
            success=True,
            error_count=0,
            audit_hash="hash123",
            metadata={"key": "value"}
        )
        
        message = self.publisher._prepare_message(record)
        
        self.assertEqual(message['run_id'], "run-123")
        self.assertEqual(message['processed_timestamp'], "2025-01-01T12:00:00")
        self.assertEqual(message['record_count'], 100)
        self.assertEqual(message['success'], True)

    def test_publish(self):
        record = AuditRecord(
            run_id="run-123",
            pipeline_name="test-pipeline",
            entity_type="applications",
            source_file="gs://bucket/file.csv",
            record_count=100,
            processed_timestamp=datetime(2025, 1, 1, 12, 0, 0),
            processing_duration_seconds=10.5,
            success=True,
            error_count=0,
            audit_hash="hash123",
            metadata={}
        )
        
        self.mock_pubsub.publish_event.return_value = "msg-id-123"
        
        msg_id = self.publisher.publish(record)
        
        self.assertEqual(msg_id, "msg-id-123")
        self.mock_pubsub.publish_event.assert_called_once()
        args, _ = self.mock_pubsub.publish_event.call_args
        self.assertEqual(args[0], self.topic_name)
        self.assertEqual(args[1]['run_id'], "run-123")

if __name__ == '__main__':
    unittest.main()

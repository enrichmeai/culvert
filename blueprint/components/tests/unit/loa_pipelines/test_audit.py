from gdw_data_core.testing import BaseGDWTest, BaseBeamTest
from gdw_data_core.core.audit import AuditTrail, DuplicateDetector
from blueprint.components.loa_domain.validation import validate_application_record

class TestAuditTrail(BaseGDWTest):
    def test_audit_trail_lifecycle(self):
        audit = AuditTrail(run_id='test_001', pipeline_name='loa_jcl', entity_type='applications')
        audit.record_processing_start('gs://bucket/applications.csv')
        
        audit.increment_counts(valid=100, errors=5)
        
        record = audit.record_processing_end(success=True)
        
        self.assertIsNotNone(record.audit_hash)
        self.assertEqual(record.record_count, 105)
    
    def test_duplicate_detector(self):
        detector = DuplicateDetector()
        
        record1 = {'id': '1', 'name': 'John'}
        record2 = {'id': '1', 'name': 'John'}
        record3 = {'id': '2', 'name': 'Jane'}
        
        # First record should not be duplicate
        is_dup1 = detector.is_duplicate(record1, key_fields=['id', 'name'])
        self.assertFalse(is_dup1)
        
        # Second identical should be duplicate
        is_dup2 = detector.is_duplicate(record2, key_fields=['id', 'name'])
        self.assertTrue(is_dup2)
        
        # Different record should not be duplicate
        is_dup3 = detector.is_duplicate(record3, key_fields=['id', 'name'])
        self.assertFalse(is_dup3)

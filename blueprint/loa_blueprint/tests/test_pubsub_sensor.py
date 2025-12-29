import unittest
from unittest.mock import MagicMock, patch
from loa_blueprint.orchestration.pubsub import LOAPubSubPullSensor

class TestLOAPubSubPullSensor(unittest.TestCase):
    def test_execute_metadata_extraction(self):
        # Mock context and task instance
        mock_ti = MagicMock()
        context = {'ti': mock_ti}
        
        # Mock messages from PubSub
        mock_messages = [
            {
                'message': {
                    'attributes': {
                        'gcs_path': 'gs://bucket/file.csv',
                        'system_id': 'SYS001',
                        'entity_type': 'applications'
                    },
                    'publishTime': '2023-01-01T00:00:00Z',
                    'messageId': 'msg123'
                }
            }
        ]
        
        # Patch the super().execute call
        with patch('airflow.providers.google.cloud.sensors.pubsub.PubSubPullSensor.execute', return_value=mock_messages):
            sensor = LOAPubSubPullSensor(
                task_id='test_sensor',
                project_id='test-project',
                subscription='test-sub'
            )
            
            result = sensor.execute(context)
            
            # Verify results
            self.assertEqual(result, mock_messages)
            
            # Verify XCom push
            mock_ti.xcom_push.assert_called_once()
            args, kwargs = mock_ti.xcom_push.call_args
            self.assertEqual(kwargs['key'], 'loa_metadata')
            metadata = kwargs['value']
            self.assertEqual(metadata['gcs_path'], 'gs://bucket/file.csv')
            self.assertEqual(metadata['system_id'], 'SYS001')
            self.assertEqual(metadata['entity_type'], 'applications')

if __name__ == '__main__':
    unittest.main()

import pytest

# Skip entire module if airflow is not installed
pytest.importorskip("airflow", reason="apache-airflow required for sensor tests")

import pytest
from unittest.mock import MagicMock, patch
from gcp_pipeline_orchestration.sensors.pubsub import PubSubCompletionSensor
from gcp_pipeline_orchestration.sensors.dataflow import DataflowStreamingSensor
from gcp_pipeline_orchestration.hooks.secrets import SecretManagerHook

class TestOrchestrationSensors:
    @patch('gcp_pipeline_orchestration.sensors.pubsub.BasePubSubPullSensor.execute')
    def test_pubsub_completion_sensor(self, mock_super_execute):
        # Mock message with expected status
        mock_super_execute.return_value = [{
            'message': {
                'attributes': {'status': 'SUCCESS', 'run_id': '123'}
            }
        }]
        
        sensor = PubSubCompletionSensor(
            task_id='test_sensor',
            project_id='test-project',
            subscription='test-sub',
            expected_status='SUCCESS'
        )
        
        context = MagicMock()
        results = sensor.execute(context)
        
        assert results is not None
        assert results[0]['message']['attributes']['status'] == 'SUCCESS'

    @patch('airflow.providers.google.cloud.hooks.bigquery.BigQueryHook.__init__', return_value=None)
    @patch('airflow.providers.google.cloud.hooks.bigquery.BigQueryHook.get_first')
    def test_dataflow_streaming_sensor(self, mock_get_first, mock_hook_init):
        from datetime import datetime, timezone

        # Recent heartbeat (staleness = 5 mins)
        mock_get_first.side_effect = [
            (datetime.now(tz=timezone.utc),), # first call in poke
            (5,) # second call (staleness)
        ]
        
        sensor = DataflowStreamingSensor(
            task_id='test_streaming_sensor',
            audit_table='project.dataset.audit',
            pipeline_name='test-pipeline',
            heartbeat_interval_minutes=15
        )
        
        # Poke should return True
        assert sensor.poke({}) is True
        
        # Old heartbeat (staleness = 20 mins)
        mock_get_first.side_effect = [
            (datetime.now(tz=timezone.utc),),
            (20,)
        ]
        
        # Poke should raise ValueError
        with pytest.raises(ValueError, match="heartbeat is stale"):
            sensor.poke({})

    @patch('google.cloud.secretmanager.SecretManagerServiceClient')
    def test_secret_manager_hook(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.payload.data = b"secret-value"
        mock_client.access_secret_version.return_value = mock_response
        
        # Test in non-airflow mode for simplicity (hook logic is similar)
        with patch('gcp_pipeline_orchestration.hooks.secrets.AIRFLOW_AVAILABLE', False):
            hook = SecretManagerHook()
            val = hook.get_secret("my-secret", project_id="test-project")
            
            assert val == "secret-value"
            mock_client.access_secret_version.assert_called_once()

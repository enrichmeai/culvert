import pytest

# Skip entire module if airflow is not installed
pytest.importorskip("airflow", reason="apache-airflow required for sensor tests")

import pytest
from unittest.mock import MagicMock, patch, call
from gcp_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor, PubSubCompletionSensor
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


def _make_ok_message():
    """Helper: Pub/Sub message for a .ok file."""
    return {
        'message': {
            'attributes': {
                'objectId': 'generic/customers/generic_customers_20260325.ok',
                'bucketId': 'my-bucket',
                'eventType': 'OBJECT_FINALIZE',
            },
            'data': '',
        }
    }


def _make_csv_message():
    """Helper: Pub/Sub message for a .csv file."""
    return {
        'message': {
            'attributes': {
                'objectId': 'generic/customers/generic_customers_20260325.csv',
                'bucketId': 'my-bucket',
                'eventType': 'OBJECT_FINALIZE',
            },
            'data': '',
        }
    }


class TestBasePubSubPullSensorPoke:
    """Tests for the filter-before-ack poke() override."""

    def _make_sensor(self, filter_extension='.ok', max_messages=10):
        return BasePubSubPullSensor(
            task_id='test_sensor',
            project_id='test-project',
            subscription='test-sub',
            filter_extension=filter_extension,
            max_messages=max_messages,
        )

    @patch('gcp_pipeline_orchestration.sensors.pubsub.PubSubHook')
    def test_poke_csv_only_returns_false(self, mock_hook_cls):
        """When only .csv messages are pulled, poke returns False (keep looking)."""
        mock_hook = mock_hook_cls.return_value
        # Simulate raw ReceivedMessage objects from hook.pull
        raw_msg = MagicMock()
        mock_hook.pull.return_value = [raw_msg]

        sensor = self._make_sensor()
        # _default_message_callback converts raw messages to dicts
        sensor._default_message_callback = MagicMock(return_value=[_make_csv_message()])

        result = sensor.poke({})

        assert result is False
        # Non-matching messages should still be acked to clear them
        mock_hook.acknowledge.assert_called_once()

    @patch('gcp_pipeline_orchestration.sensors.pubsub.PubSubHook')
    def test_poke_ok_message_returns_true(self, mock_hook_cls):
        """When a .ok message is pulled, poke returns True."""
        mock_hook = mock_hook_cls.return_value
        raw_msg = MagicMock()
        mock_hook.pull.return_value = [raw_msg]

        sensor = self._make_sensor()
        sensor._default_message_callback = MagicMock(return_value=[_make_ok_message()])

        result = sensor.poke({})

        assert result is True
        assert sensor._return_value == [_make_ok_message()]
        mock_hook.acknowledge.assert_called_once()

    @patch('gcp_pipeline_orchestration.sensors.pubsub.PubSubHook')
    def test_poke_mixed_messages_returns_only_ok(self, mock_hook_cls):
        """When both .csv and .ok messages are pulled, only .ok is in _return_value."""
        mock_hook = mock_hook_cls.return_value
        raw_msgs = [MagicMock(), MagicMock()]
        mock_hook.pull.return_value = raw_msgs

        sensor = self._make_sensor()
        sensor._default_message_callback = MagicMock(
            return_value=[_make_csv_message(), _make_ok_message()]
        )

        result = sensor.poke({})

        assert result is True
        assert len(sensor._return_value) == 1
        assert sensor._return_value[0]['message']['attributes']['objectId'].endswith('.ok')
        # All raw messages acked (both .csv and .ok)
        mock_hook.acknowledge.assert_called_once_with(
            project_id='test-project',
            subscription='test-sub',
            messages=raw_msgs,
        )

    @patch('gcp_pipeline_orchestration.sensors.pubsub.PubSubHook')
    def test_poke_no_messages_returns_false(self, mock_hook_cls):
        """When no messages are available, poke returns False."""
        mock_hook = mock_hook_cls.return_value
        mock_hook.pull.return_value = []

        sensor = self._make_sensor()
        result = sensor.poke({})

        assert result is False
        mock_hook.acknowledge.assert_not_called()

    def test_poke_no_filter_delegates_to_parent(self):
        """When filter_extension is None, poke delegates to parent."""
        sensor = self._make_sensor(filter_extension=None)
        with patch.object(type(sensor).__bases__[0], 'poke', return_value=True) as mock_parent:
            result = sensor.poke({})
            assert result is True
            mock_parent.assert_called_once()

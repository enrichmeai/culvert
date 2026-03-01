import pytest
import json
from unittest.mock import MagicMock, patch
from gcp_pipeline_beam.pipelines.beam.pubsub.publishers import PublishToPubSubDoFn

class TestPublishToPubSubDoFn:
    @patch('google.cloud.pubsub_v1.PublisherClient')
    def test_publish_async(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_future = MagicMock()
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = 'projects/test-project/topics/test-topic'

        do_fn = PublishToPubSubDoFn(project='test-project', topic='test-topic')
        do_fn.setup()

        element = {'id': 1, 'data': 'test'}
        results = list(do_fn.process(element))

        # Verify publish was called
        mock_client.publish.assert_called_once_with(
            'projects/test-project/topics/test-topic',
            json.dumps(element).encode('utf-8')
        )

        # Verify callback was added
        mock_future.add_done_callback.assert_called_once()

        # Verify element was yielded (for chaining)
        assert results == [element]

    def test_callback_success(self):
        do_fn = PublishToPubSubDoFn(project='test-project', topic='test-topic')
        mock_future = MagicMock()
        mock_future.result.return_value = 'msg-id-123'

        # Manually trigger callback
        do_fn._callback(mock_future)

        # In a real scenario we'd check metrics, but here we just ensure no exception
        assert True

    def test_callback_failure(self):
        do_fn = PublishToPubSubDoFn(project='test-project', topic='test-topic')
        mock_future = MagicMock()
        mock_future.result.side_effect = Exception("PubSub Error")

        # Should not raise exception (handled in callback)
        do_fn._callback(mock_future)
        assert True

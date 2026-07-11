"""End-to-end failure-routing tests (T11.2d / #87, DoD #2).

Unlike ``test_handlers.py`` — which mocks ``publish_to_dlq`` / ``quarantine_file``
at the handler boundary — these tests stub the *underlying* GCP clients
(``PubSubClient`` / ``google.cloud.storage.Client``) and exercise the real
``publish_to_dlq`` and ``quarantine_file`` code paths. They prove that a failed
task is actually routed to the DLQ topic and the quarantine bucket.
"""

import unittest
from unittest.mock import MagicMock, patch

from data_pipeline_orchestration.callbacks import (
    ErrorHandlerConfig,
    ErrorType,
    on_failure_callback,
    on_validation_failure,
    quarantine_file,
)


def _fake_context(task_id="run_dataflow_pipeline", exc=None):
    ti = MagicMock()
    ti.task_id = task_id
    ti.dag_id = "generic_customer_account_transformation_dag"
    ti.try_number = 1
    ti.xcom_pull.return_value = None
    return {
        "ti": ti,
        "run_id": "transform_customer_account_20260101",
        "execution_date": None,
        "exception": exc,
    }


class TestFailureRoutesToDLQ(unittest.TestCase):
    """A failed task's on_failure_callback publishes to the DLQ topic."""

    @patch("data_pipeline_orchestration.callbacks.dlq._get_project_id", return_value="proj-123")
    @patch("google.cloud.pubsub_v1.PublisherClient")
    def test_failure_callback_publishes_to_dlq_topic(self, mock_client_cls, _proj):
        import json

        stub_client = MagicMock()
        stub_client.topic_path.side_effect = (
            lambda project, topic: f"projects/{project}/topics/{topic}")
        stub_client.publish.return_value.result.return_value = "msg-id-987"
        mock_client_cls.return_value = stub_client

        cfg = ErrorHandlerConfig(dlq_topic="generic-dlq")
        ctx = _fake_context(exc=ValueError("dataflow boom"))

        # on_failure_callback → publish_to_dlq → PublisherClient.publish
        on_failure_callback(ctx, cfg)

        stub_client.publish.assert_called_once()
        args = stub_client.publish.call_args
        self.assertEqual(args.args[0], "projects/proj-123/topics/generic-dlq")
        payload = json.loads(args.args[1].decode("utf-8"))
        self.assertIn("dataflow boom", payload["error_message"])
        self.assertEqual(args.kwargs["error_type"], str(ErrorType.TASK_FAILURE))

    @patch("google.cloud.pubsub_v1.PublisherClient")
    def test_disabled_dlq_does_not_publish(self, mock_client_cls):
        cfg = ErrorHandlerConfig(enable_dlq=False)
        on_failure_callback(_fake_context(exc=RuntimeError("x")), cfg)
        mock_client_cls.assert_not_called()


class TestFailureRoutesToQuarantine(unittest.TestCase):
    """A validation failure quarantines the offending file via storage client."""

    @patch("data_pipeline_orchestration.callbacks.quarantine._get_project_id", return_value="proj-123")
    @patch("data_pipeline_orchestration.callbacks.handlers.publish_to_dlq", return_value="msg-id")
    @patch("google.cloud.storage.Client")
    def test_validation_failure_quarantines_file(self, mock_storage_cls, _pub, _proj):
        client = MagicMock()
        mock_storage_cls.return_value = client

        cfg = ErrorHandlerConfig(quarantine_bucket="generic-quarantine")
        ctx = _fake_context(task_id="validate_file")

        on_validation_failure(
            ctx, ["missing column id"], "gs://generic-landing/data/file.csv",
            quarantine=True, config=cfg,
        )

        # copy_blob to quarantine bucket then delete the source
        client.bucket.assert_any_call("generic-landing")
        client.bucket.assert_any_call("generic-quarantine")
        src_bucket = client.bucket.return_value
        src_bucket.copy_blob.assert_called_once()
        src_bucket.blob.return_value.delete.assert_called_once()

    @patch("data_pipeline_orchestration.callbacks.quarantine._get_project_id", return_value="proj-123")
    @patch("google.cloud.storage.Client")
    def test_quarantine_returns_new_gcs_path(self, mock_storage_cls, _proj):
        mock_storage_cls.return_value = MagicMock()
        cfg = ErrorHandlerConfig(quarantine_bucket="generic-quarantine")

        new_path = quarantine_file(
            _fake_context(), "gs://generic-landing/data/file.csv",
            reason="validation_failure", config=cfg,
        )

        self.assertIsNotNone(new_path)
        self.assertTrue(new_path.startswith("gs://generic-quarantine/validation_failure/"))
        self.assertTrue(new_path.endswith("data/file.csv"))


if __name__ == "__main__":
    unittest.main()

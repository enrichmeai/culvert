"""Unit tests for alert backends — Dynatrace, ServiceNow, Cloud Monitoring."""

import unittest
from unittest.mock import patch, MagicMock

from gcp_pipeline_core.monitoring.alerts import (
    AlertManager,
    LoggingAlertBackend,
    DynatraceAlertBackend,
    ServiceNowAlertBackend,
    CloudMonitoringBackend,
)
from gcp_pipeline_core.monitoring.types import Alert, AlertLevel


def _make_alert(level=AlertLevel.CRITICAL, title="Test Alert", message="test"):
    """Helper to create a test Alert."""
    return Alert(
        alert_id="alert_123",
        level=level,
        title=title,
        message=message,
        source="test_dag",
        metadata={"run_id": "run_001"},
    )


class TestAlertManager(unittest.TestCase):
    """Test AlertManager routes to all backends."""

    def test_create_alert_calls_all_backends(self):
        backend1 = MagicMock()
        backend2 = MagicMock()
        mgr = AlertManager(alert_backends=[backend1, backend2])
        alert = mgr.create_alert(
            level=AlertLevel.CRITICAL,
            title="Fail",
            message="task failed",
            source="dag",
        )
        backend1.send_alert.assert_called_once()
        backend2.send_alert.assert_called_once()
        self.assertEqual(alert.title, "Fail")

    def test_backend_exception_does_not_break_others(self):
        failing = MagicMock()
        failing.send_alert.side_effect = RuntimeError("boom")
        working = MagicMock()
        mgr = AlertManager(alert_backends=[failing, working])
        mgr.create_alert(
            level=AlertLevel.WARNING,
            title="T",
            message="m",
            source="s",
        )
        working.send_alert.assert_called_once()

    def test_get_recent_alerts(self):
        mgr = AlertManager(alert_backends=[])
        mgr.create_alert(level=AlertLevel.INFO, title="A", message="m", source="s")
        mgr.create_alert(level=AlertLevel.CRITICAL, title="B", message="m", source="s")
        self.assertEqual(len(mgr.get_recent_alerts(minutes=1)), 2)
        self.assertEqual(len(mgr.get_recent_alerts(minutes=1, level=AlertLevel.CRITICAL)), 1)


class TestDynatraceAlertBackend(unittest.TestCase):
    """Test DynatraceAlertBackend sends events via Events API v2."""

    @patch("requests.post")
    def test_send_critical_alert(self, mock_post):
        mock_post.return_value = MagicMock()

        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.test",
        )
        result = backend.send_alert(_make_alert(level=AlertLevel.CRITICAL, title="Pipeline Down"))

        self.assertTrue(result)
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertIn("/api/v2/events/ingest", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["eventType"], "ERROR_EVENT")
        self.assertEqual(payload["title"], "Pipeline Down")

    @patch("requests.post")
    def test_send_warning_maps_to_custom_alert(self, mock_post):
        mock_post.return_value = MagicMock()
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.test",
        )
        backend.send_alert(_make_alert(level=AlertLevel.WARNING))
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["eventType"], "CUSTOM_ALERT")

    @patch("requests.post")
    def test_send_info_maps_to_custom_info(self, mock_post):
        mock_post.return_value = MagicMock()
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.test",
        )
        backend.send_alert(_make_alert(level=AlertLevel.INFO))
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["eventType"], "CUSTOM_INFO")

    @patch("requests.post")
    def test_auth_header_set(self, mock_post):
        mock_post.return_value = MagicMock()
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.secret",
        )
        backend.send_alert(_make_alert())
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Api-Token dt0c01.secret")

    @patch("requests.post")
    def test_metadata_in_properties(self, mock_post):
        mock_post.return_value = MagicMock()
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.test",
        )
        alert = _make_alert()
        alert.metadata = {"run_id": "run_001", "entity": "customers"}
        backend.send_alert(alert)
        props = mock_post.call_args[1]["json"]["properties"]
        self.assertEqual(props["run_id"], "run_001")
        self.assertEqual(props["entity"], "customers")

    @patch("requests.post")
    def test_failure_returns_false(self, mock_post):
        mock_post.side_effect = Exception("connection timeout")
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com",
            api_token="dt0c01.test",
        )
        result = backend.send_alert(_make_alert())
        self.assertFalse(result)

    def test_trailing_slash_stripped(self):
        backend = DynatraceAlertBackend(
            environment_url="https://xyz.live.dynatrace.com/",
            api_token="dt0c01.test",
        )
        self.assertEqual(backend.environment_url, "https://xyz.live.dynatrace.com")


class TestServiceNowAlertBackend(unittest.TestCase):
    """Test ServiceNowAlertBackend creates incidents via Table API."""

    @patch("requests.post")
    def test_create_critical_incident(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "INC0012345"}}
        mock_post.return_value = mock_response

        backend = ServiceNowAlertBackend(
            instance_url="https://mycompany.service-now.com",
            username="api_user",
            password="api_pass",
            assignment_group="Data Engineering",
        )
        result = backend.send_alert(_make_alert(level=AlertLevel.CRITICAL))

        self.assertTrue(result)
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertIn("/api/now/table/incident", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["impact"], "1")
        self.assertEqual(payload["urgency"], "1")
        self.assertEqual(payload["category"], "Data Pipeline")
        self.assertEqual(payload["assignment_group"], "Data Engineering")

    @patch("requests.post")
    def test_warning_maps_to_impact_2(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "INC0012346"}}
        mock_post.return_value = mock_response

        backend = ServiceNowAlertBackend(
            instance_url="https://mycompany.service-now.com",
            username="u",
            password="p",
        )
        backend.send_alert(_make_alert(level=AlertLevel.WARNING))
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["impact"], "2")
        self.assertEqual(payload["urgency"], "2")

    @patch("requests.post")
    def test_basic_auth_used(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "INC001"}}
        mock_post.return_value = mock_response

        backend = ServiceNowAlertBackend(
            instance_url="https://mycompany.service-now.com",
            username="api_user",
            password="api_pass",
        )
        backend.send_alert(_make_alert())
        auth = mock_post.call_args[1]["auth"]
        self.assertEqual(auth, ("api_user", "api_pass"))

    @patch("requests.post")
    def test_metadata_in_description(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "INC001"}}
        mock_post.return_value = mock_response

        backend = ServiceNowAlertBackend(
            instance_url="https://mycompany.service-now.com",
            username="u",
            password="p",
        )
        alert = _make_alert()
        alert.metadata = {"run_id": "run_001"}
        backend.send_alert(alert)
        desc = mock_post.call_args[1]["json"]["description"]
        self.assertIn("run_id: run_001", desc)

    @patch("requests.post")
    def test_failure_returns_false(self, mock_post):
        mock_post.side_effect = Exception("connection refused")
        backend = ServiceNowAlertBackend(
            instance_url="https://mycompany.service-now.com",
            username="u",
            password="p",
        )
        result = backend.send_alert(_make_alert())
        self.assertFalse(result)


class TestLoggingAlertBackend(unittest.TestCase):
    """Test LoggingAlertBackend."""

    def test_always_returns_true(self):
        backend = LoggingAlertBackend()
        self.assertTrue(backend.send_alert(_make_alert(AlertLevel.CRITICAL)))
        self.assertTrue(backend.send_alert(_make_alert(AlertLevel.WARNING)))
        self.assertTrue(backend.send_alert(_make_alert(AlertLevel.INFO)))


if __name__ == "__main__":
    unittest.main()

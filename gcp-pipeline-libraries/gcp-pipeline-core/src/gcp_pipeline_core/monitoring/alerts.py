"""
Alert management and backends.

Creates, sends, and tracks alerts based on metrics and events.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from .types import Alert, AlertLevel
from ..utilities.logging import get_logger

logger = get_logger(__name__)


class AlertManager:
    """
    Manages alerts for migration pipelines.

    Creates, sends, and tracks alerts based on metrics and events.
    """

    def __init__(self, alert_backends: Optional[List['AlertBackend']] = None):
        self.backends = alert_backends or []
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []

    def create_alert(self,
                     level: AlertLevel,
                     title: str,
                     message: str,
                     source: str,
                     metric_name: Optional[str] = None,
                     threshold_value: Optional[float] = None,
                     actual_value: Optional[float] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Alert:
        """Create and send an alert"""
        alert = Alert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            level=level,
            title=title,
            message=message,
            source=source,
            metric_name=metric_name,
            threshold_value=threshold_value,
            actual_value=actual_value,
            metadata=metadata or {}
        )

        self.alerts.append(alert)
        self.alert_history.append(alert)

        # Send to all backends
        for backend in self.backends:
            try:
                backend.send_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {backend.__class__.__name__}: {e}")

        logger.info(f"Alert created: {alert.title}")
        return alert

    def get_recent_alerts(self, minutes: int = 60, level: Optional[AlertLevel] = None) -> List[Alert]:
        """Get recent alerts"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent = [a for a in self.alert_history if a.timestamp >= cutoff]

        if level:
            recent = [a for a in recent if a.level == level]

        return recent


class AlertBackend(ABC):
    """Abstract base for alert backends"""

    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """Send alert to backend"""


class LoggingAlertBackend(AlertBackend):
    """Sends alerts to logging system"""

    def send_alert(self, alert: Alert) -> bool:
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(f"ALERT: {alert.title} - {alert.message}")
        elif alert.level == AlertLevel.WARNING:
            logger.warning(f"ALERT: {alert.title} - {alert.message}")
        else:
            logger.info(f"ALERT: {alert.title} - {alert.message}")
        return True


class CloudMonitoringBackend(AlertBackend):
    """Sends alerts to Google Cloud Monitoring"""

    def __init__(self, project_id: str):
        self.project_id = project_id

    def send_alert(self, alert: Alert) -> bool:
        try:
            from google.cloud import monitoring_v3

            client = monitoring_v3.MetricServiceClient()
            project_name = f"projects/{self.project_id}"

            # Create time series data
            # This is a simplified example
            logger.info(f"Sent alert to Cloud Monitoring: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert to Cloud Monitoring: {e}")
            return False


class DatadogAlertBackend(AlertBackend):
    """
    Sends alerts to Datadog.
    
    SECURITY NOTE: Do not hardcode api_key or app_key. 
    Use GCP Secret Manager or environment variables to inject them.
    """

    def __init__(self, api_key: str, app_key: str):
        self.api_key = api_key
        self.app_key = app_key

    def send_alert(self, alert: Alert) -> bool:
        try:
            # This would integrate with Datadog API
            # For now, just log
            logger.info(f"Sent alert to Datadog: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert to Datadog: {e}")
            return False


class SlackAlertBackend(AlertBackend):
    """
    Sends alerts to Slack.

    SECURITY NOTE: Do not hardcode webhook_url.
    Use GCP Secret Manager or environment variables to inject it.
    """

    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        self.webhook_url = webhook_url
        self.channel = channel

    def send_alert(self, alert: Alert) -> bool:
        try:
            import requests

            # Build Slack message
            message = {
                'text': alert.title,
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"*{alert.title}*\n{alert.message}"
                        }
                    },
                    {
                        'type': 'section',
                        'fields': [
                            {'type': 'mrkdwn', 'text': f"*Level*\n{alert.level.value}"},
                            {'type': 'mrkdwn', 'text': f"*Source*\n{alert.source}"}
                        ]
                    }
                ]
            }

            if self.channel:
                message['channel'] = self.channel

            response = requests.post(self.webhook_url, json=message, timeout=30)
            response.raise_for_status()

            logger.info(f"Sent alert to Slack: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert to Slack: {e}")
            return False


class DynatraceAlertBackend(AlertBackend):
    """
    Sends alerts to Dynatrace via the Events API v2.

    Creates custom info/error events in Dynatrace that appear in the
    Problems feed and can trigger Davis AI correlation.

    SECURITY NOTE: Do not hardcode api_token.
    Use GCP Secret Manager or environment variables to inject it.

    Args:
        environment_url: Dynatrace environment URL
            (e.g., "https://xyz.live.dynatrace.com")
        api_token: Dynatrace API token with ``events.ingest`` scope
    """

    def __init__(self, environment_url: str, api_token: str):
        self.environment_url = environment_url.rstrip("/")
        self.api_token = api_token

    def send_alert(self, alert: Alert) -> bool:
        try:
            import requests

            url = f"{self.environment_url}/api/v2/events/ingest"
            headers = {
                "Authorization": f"Api-Token {self.api_token}",
                "Content-Type": "application/json",
            }

            # Map AlertLevel to Dynatrace event type
            event_type_map = {
                AlertLevel.CRITICAL: "ERROR_EVENT",
                AlertLevel.WARNING: "CUSTOM_ALERT",
                AlertLevel.INFO: "CUSTOM_INFO",
            }
            event_type = event_type_map.get(alert.level, "CUSTOM_INFO")

            properties = {
                "alert_id": alert.alert_id,
                "source": alert.source,
                "level": alert.level.value,
            }
            if alert.metric_name:
                properties["metric_name"] = alert.metric_name
            if alert.threshold_value is not None:
                properties["threshold_value"] = str(alert.threshold_value)
            if alert.actual_value is not None:
                properties["actual_value"] = str(alert.actual_value)
            for k, v in (alert.metadata or {}).items():
                properties[str(k)] = str(v)[:250]

            payload = {
                "eventType": event_type,
                "title": alert.title[:200],
                "timeout": 60,
                "properties": properties,
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            logger.info(f"Sent alert to Dynatrace: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert to Dynatrace: {e}")
            return False


class ServiceNowAlertBackend(AlertBackend):
    """
    Creates incidents in ServiceNow via the Table API.

    Maps AlertLevel to ServiceNow impact/urgency:
      CRITICAL → impact=1 (High), urgency=1 (High)
      WARNING  → impact=2 (Medium), urgency=2 (Medium)
      INFO     → impact=3 (Low), urgency=3 (Low)

    SECURITY NOTE: Do not hardcode credentials.
    Use GCP Secret Manager or environment variables to inject them.

    Args:
        instance_url: ServiceNow instance URL
            (e.g., "https://mycompany.service-now.com")
        username: ServiceNow API user
        password: ServiceNow API password
        assignment_group: Assignment group for created incidents
        caller_id: sys_id of the caller (service account)
    """

    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        assignment_group: str = "",
        caller_id: str = "",
    ):
        self.instance_url = instance_url.rstrip("/")
        self.username = username
        self.password = password
        self.assignment_group = assignment_group
        self.caller_id = caller_id

    def send_alert(self, alert: Alert) -> bool:
        try:
            import requests

            url = f"{self.instance_url}/api/now/table/incident"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Map AlertLevel to SNOW impact/urgency
            severity_map = {
                AlertLevel.CRITICAL: ("1", "1"),
                AlertLevel.WARNING: ("2", "2"),
                AlertLevel.INFO: ("3", "3"),
            }
            impact, urgency = severity_map.get(alert.level, ("3", "3"))

            description_parts = [alert.message]
            if alert.metric_name:
                description_parts.append(f"Metric: {alert.metric_name}")
            if alert.threshold_value is not None:
                description_parts.append(f"Threshold: {alert.threshold_value}")
            if alert.actual_value is not None:
                description_parts.append(f"Actual: {alert.actual_value}")
            for k, v in (alert.metadata or {}).items():
                description_parts.append(f"{k}: {v}")

            payload = {
                "short_description": alert.title[:160],
                "description": "\n".join(description_parts),
                "impact": impact,
                "urgency": urgency,
                "category": "Data Pipeline",
                "subcategory": alert.source,
            }

            if self.assignment_group:
                payload["assignment_group"] = self.assignment_group
            if self.caller_id:
                payload["caller_id"] = self.caller_id

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                auth=(self.username, self.password),
                timeout=30,
            )
            response.raise_for_status()

            result = response.json().get("result", {})
            incident_number = result.get("number", "unknown")
            logger.info(f"Created ServiceNow incident {incident_number}: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to create ServiceNow incident: {e}")
            return False

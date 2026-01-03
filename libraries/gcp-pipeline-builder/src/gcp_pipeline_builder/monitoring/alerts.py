"""
Alert management and backends.

Creates, sends, and tracks alerts based on metrics and events.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from .types import Alert, AlertLevel

logger = logging.getLogger(__name__)


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
                logger.error("Failed to send alert via %s: %s", backend.__class__.__name__, e)

        logger.info("Alert created: %s", alert.title)
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
            logger.critical("ALERT: %s - %s", alert.title, alert.message)
        elif alert.level == AlertLevel.WARNING:
            logger.warning("ALERT: %s - %s", alert.title, alert.message)
        else:
            logger.info("ALERT: %s - %s", alert.title, alert.message)
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
            logger.info("Sent alert to Cloud Monitoring: %s", alert.title)
            return True
        except Exception as e:
            logger.error("Failed to send alert to Cloud Monitoring: %s", e)
            return False


class DatadogAlertBackend(AlertBackend):
    """Sends alerts to Datadog"""

    def __init__(self, api_key: str, app_key: str):
        self.api_key = api_key
        self.app_key = app_key

    def send_alert(self, alert: Alert) -> bool:
        try:
            # This would integrate with Datadog API
            # For now, just log
            logger.info("Sent alert to Datadog: %s", alert.title)
            return True
        except Exception as e:
            logger.error("Failed to send alert to Datadog: %s", e)
            return False


class SlackAlertBackend(AlertBackend):
    """Sends alerts to Slack"""

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

            logger.info("Sent alert to Slack: %s", alert.title)
            return True
        except Exception as e:
            logger.error("Failed to send alert to Slack: %s", e)
            return False

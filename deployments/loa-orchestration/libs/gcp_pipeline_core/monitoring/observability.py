"""
High-level observability management combining metrics, health, and alerts.

Main interface for pipelines to report metrics and health.
"""

import json
from typing import Dict, Any, List

from .metrics import MetricsCollector
from .health import HealthChecker
from .alerts import AlertManager, AlertBackend, LoggingAlertBackend
from .types import AlertLevel


class ObservabilityManager:
    """
    High-level observability manager combining metrics, health, and alerts.

    This is the main interface for pipelines to report metrics and health.
    """

    def __init__(self,
                 pipeline_name: str,
                 run_id: str,
                 alert_backends: List[AlertBackend] = None):
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        self.metrics = MetricsCollector(pipeline_name, run_id)
        self.health = HealthChecker(self.metrics)
        self.alerts = AlertManager(alert_backends or [LoggingAlertBackend()])

    def report_records_processed(self, count: int, labels: Dict[str, str] = None):
        """Report records processed"""
        self.metrics.increment('records_processed', count, labels)

    def report_records_error(self, count: int, labels: Dict[str, str] = None):
        """Report record errors"""
        self.metrics.increment('records_error', count, labels)

    def report_step_duration(self, step_name: str, duration_seconds: float):
        """Report step duration"""
        self.metrics.record_step_duration(step_name, duration_seconds)

    def check_health(self) -> bool:
        """Run health checks and trigger alerts if unhealthy"""
        checks = self.health.run_all_checks()

        if not self.health.is_healthy():
            unhealthy = [k for k, v in checks.items() if not v]
            self.alerts.create_alert(
                level=AlertLevel.WARNING,
                title="Pipeline Health Check Failed",
                message=f"Failed checks: {', '.join(unhealthy)}",
                source="health_checker",
                metadata={'failed_checks': unhealthy}
            )

        return self.health.is_healthy()

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of metrics and health"""
        return {
            'metrics': self.metrics.get_statistics(),
            'health': self.health.run_all_checks(),
            'is_healthy': self.health.is_healthy(),
            'recent_alerts': [a.to_dict() for a in self.alerts.get_recent_alerts(minutes=60)]
        }

    def export_metrics(self) -> str:
        """Export all metrics as JSON"""
        stats = self.metrics.get_statistics()
        return json.dumps(stats, default=str, indent=2)


"""
GDW Data Core - Monitoring & Observability Framework

Production-grade monitoring, metrics collection, and alerting.
Integrates with Google Cloud Monitoring, Datadog, and custom backends.
"""

from .types import MetricType, AlertLevel, MetricValue, Alert
from .metrics import MetricsCollector, TimerContext, MigrationMetrics
from .health import HealthChecker, HealthStatus
from .alerts import (
    AlertManager,
    AlertBackend,
    LoggingAlertBackend,
    CloudMonitoringBackend,
    DatadogAlertBackend,
    SlackAlertBackend,
)
from .observability import ObservabilityManager

__all__ = [
    # Types
    'MetricType',
    'AlertLevel',
    'MetricValue',
    'Alert',
    # Metrics
    'MetricsCollector',
    'TimerContext',
    'MigrationMetrics',
    # Health
    'HealthChecker',
    'HealthStatus',
    # Alerts
    'AlertManager',
    'AlertBackend',
    'LoggingAlertBackend',
    'CloudMonitoringBackend',
    'DatadogAlertBackend',
    'SlackAlertBackend',
    # Observability
    'ObservabilityManager',
]


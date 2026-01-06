"""
GDW Data Core - Monitoring & Observability Framework

Production-grade monitoring, metrics collection, and alerting.
Integrates with Google Cloud Monitoring, Datadog, Dynatrace, and custom backends.

OpenTelemetry Integration:
    For distributed tracing and metrics export to Dynatrace, GCP Trace, or OTLP backends,
    install with: pip install gcp-pipeline-builder[otel]

    Usage:
        from gcp_pipeline_builder.monitoring.otel import (
            OTELConfig, configure_otel, OTELContext
        )
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

# Optional OTEL exports - available when otel dependencies installed
try:
    from .otel import (
        OTELConfig,
        OTELExporterType,
        configure_otel,
        is_otel_initialized,
        get_tracer,
        get_meter,
        shutdown_otel,
        trace_function,
        trace_beam_dofn,
        OTELContext,
        SpanContext,
        OTELMetricsBridge,
    )
    _OTEL_AVAILABLE = True

    __all__.extend([
        'OTELConfig',
        'OTELExporterType',
        'configure_otel',
        'is_otel_initialized',
        'get_tracer',
        'get_meter',
        'shutdown_otel',
        'trace_function',
        'trace_beam_dofn',
        'OTELContext',
        'SpanContext',
        'OTELMetricsBridge',
    ])
except ImportError:
    _OTEL_AVAILABLE = False


def is_otel_available() -> bool:
    """Check if OTEL dependencies are installed."""
    return _OTEL_AVAILABLE


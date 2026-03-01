"""
OpenTelemetry (OTEL) Integration for GCP Pipeline Builder.

Provides distributed tracing, metrics, and logging export to:
- Dynatrace
- Google Cloud Trace
- Jaeger
- Any OTLP-compatible backend

Usage:
    from gcp_pipeline_core.monitoring.otel import (
        OTELConfig,
        configure_otel,
        get_tracer,
        get_meter,
        OTELContext,
    )

    # Configure OTEL with Dynatrace
    config = OTELConfig.for_dynatrace(
        service_name="application1-pipeline",
        dynatrace_url="https://your-env.live.dynatrace.com/api/v2/otlp",
        dynatrace_token="dt0c01.xxx",
    )
    configure_otel(config)

    # Get tracer for distributed tracing
    tracer = get_tracer("my_module")
    with tracer.start_as_current_span("process_records") as span:
        span.set_attribute("records.count", 1000)
        process_records()

    # Use context for pipeline-wide tracing
    with OTELContext(run_id="run_123", system_id="Application1") as ctx:
        with ctx.span("validation") as span:
            span.set_attribute("records", 1000)
            validate_records()

Environment Variables:
    OTEL_SERVICE_NAME: Service name (default: gcp-pipeline)
    OTEL_EXPORTER_TYPE: Exporter type (console, otlp, dynatrace, gcp_trace, none)
    DYNATRACE_OTEL_URL: Dynatrace OTLP endpoint URL
    DYNATRACE_API_TOKEN: Dynatrace API token with otlp.ingest scope
    GCP_PROJECT_ID: GCP project ID for Cloud Trace
    OTEL_SAMPLE_RATE: Trace sampling rate (0.0 to 1.0, default: 1.0)

Dependencies:
    Install with: pip install gcp-pipeline-builder[otel]
    Or for Dynatrace only: pip install gcp-pipeline-builder[dynatrace]
"""

# These modules don't require OTEL SDK - they use lazy imports
from .config import OTELConfig, OTELExporterType
from .provider import OTELProvider, get_provider, set_provider, reset_provider
from .tracing import (
    configure_otel,
    is_otel_initialized,
    get_tracer,
    get_meter,
    get_logger_provider,
    shutdown_otel,
    trace_function,
    trace_beam_dofn,
)
from .context import OTELContext, SpanContext
from .metrics_bridge import OTELMetricsBridge

__all__ = [
    # Config
    'OTELConfig',
    'OTELExporterType',
    # Provider
    'OTELProvider',
    'get_provider',
    'set_provider',
    'reset_provider',
    # Tracing
    'configure_otel',
    'is_otel_initialized',
    'get_tracer',
    'get_meter',
    'get_logger_provider',
    'shutdown_otel',
    'trace_function',
    'trace_beam_dofn',
    # Context
    'OTELContext',
    'SpanContext',
    # Bridge
    'OTELMetricsBridge',
]


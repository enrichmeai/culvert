"""
OpenTelemetry provider for initializing and managing OTEL SDK.

Handles:
- Tracer provider setup
- Meter provider setup
- Exporter configuration
- Resource attributes
"""

import atexit
import logging
from typing import Optional

from .config import OTELConfig, OTELExporterType

logger = logging.getLogger(__name__)

# Global provider instance
_provider: Optional["OTELProvider"] = None


class OTELProvider:
    """
    Manages OpenTelemetry SDK initialization and lifecycle.

    This is a singleton that should be initialized once at application startup.

    Example:
        >>> config = OTELConfig.for_dynatrace(...)
        >>> provider = OTELProvider(config)
        >>> provider.initialize()
        >>> tracer = provider.get_tracer("my_module")
    """

    def __init__(self, config: OTELConfig):
        self.config = config
        self._tracer_provider = None
        self._meter_provider = None
        self._resource = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize OTEL SDK with configured exporters.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            logger.warning("OTEL already initialized")
            return True

        if self.config.exporter_type == OTELExporterType.NONE:
            logger.info("OTEL disabled by configuration")
            return False

        try:
            self._setup_resource()
            self._setup_tracer_provider()
            self._setup_meter_provider()
            self._initialized = True

            # Register shutdown hook
            atexit.register(self.shutdown)

            logger.info(
                f"OTEL initialized: service={self.config.service_name}, "
                f"exporter={self.config.exporter_type.value}"
            )
            return True

        except ImportError as e:
            logger.warning(f"OTEL dependencies not installed: {e}")
            logger.info("Install with: pip install gcp-pipeline-builder[otel]")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize OTEL: {e}")
            return False

    def _setup_resource(self):
        """Create OTEL resource with service attributes."""
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

        attributes = {
            SERVICE_NAME: self.config.service_name,
            SERVICE_VERSION: self.config.service_version,
            "deployment.environment": self.config.environment,
            "service.namespace": "gcp-pipeline-builder",
        }
        attributes.update(self.config.resource_attributes)

        self._resource = Resource.create(attributes)

    def _setup_tracer_provider(self):
        """Configure tracer provider with appropriate exporter."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

        self._tracer_provider = TracerProvider(resource=self._resource)

        # Get exporter based on config
        exporter = self._create_trace_exporter()

        if exporter:
            if self.config.batch_export:
                processor = BatchSpanProcessor(
                    exporter,
                    max_export_batch_size=512,
                    export_timeout_millis=self.config.export_timeout_ms,
                )
            else:
                processor = SimpleSpanProcessor(exporter)

            self._tracer_provider.add_span_processor(processor)

        # Set as global provider
        trace.set_tracer_provider(self._tracer_provider)

    def _setup_meter_provider(self):
        """Configure meter provider with appropriate exporter."""
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        readers = []
        exporter = self._create_metrics_exporter()

        if exporter:
            reader = PeriodicExportingMetricReader(
                exporter,
                export_interval_millis=60000,  # Export every 60 seconds
                export_timeout_millis=self.config.export_timeout_ms,
            )
            readers.append(reader)

        self._meter_provider = MeterProvider(
            resource=self._resource,
            metric_readers=readers,
        )

        # Set as global provider
        metrics.set_meter_provider(self._meter_provider)

    def _create_trace_exporter(self):
        """Create trace exporter based on configuration."""
        exporter_type = self.config.exporter_type

        if exporter_type == OTELExporterType.CONSOLE:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            return ConsoleSpanExporter()

        elif exporter_type in (OTELExporterType.DYNATRACE, OTELExporterType.OTLP_HTTP):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint = self.config.dynatrace_url or self.config.otlp_endpoint
            headers = {}

            if self.config.dynatrace_token:
                headers["Authorization"] = f"Api-Token {self.config.dynatrace_token}"

            return OTLPSpanExporter(
                endpoint=f"{endpoint}/v1/traces",
                headers=headers,
                timeout=self.config.export_timeout_ms // 1000,
            )

        elif exporter_type == OTELExporterType.OTLP:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            return OTLPSpanExporter(
                endpoint=self.config.otlp_endpoint,
                timeout=self.config.export_timeout_ms // 1000,
            )

        elif exporter_type == OTELExporterType.GCP_TRACE:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            return CloudTraceSpanExporter(project_id=self.config.gcp_project_id)

        return None

    def _create_metrics_exporter(self):
        """Create metrics exporter based on configuration."""
        exporter_type = self.config.exporter_type

        if exporter_type == OTELExporterType.CONSOLE:
            from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
            return ConsoleMetricExporter()

        elif exporter_type in (OTELExporterType.DYNATRACE, OTELExporterType.OTLP_HTTP):
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

            endpoint = self.config.dynatrace_url or self.config.otlp_endpoint
            headers = {}

            if self.config.dynatrace_token:
                headers["Authorization"] = f"Api-Token {self.config.dynatrace_token}"

            return OTLPMetricExporter(
                endpoint=f"{endpoint}/v1/metrics",
                headers=headers,
                timeout=self.config.export_timeout_ms // 1000,
            )

        elif exporter_type == OTELExporterType.OTLP:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            return OTLPMetricExporter(
                endpoint=self.config.otlp_endpoint,
                timeout=self.config.export_timeout_ms // 1000,
            )

        return None

    def get_tracer(self, name: str):
        """Get a tracer for the given module name."""
        from opentelemetry import trace
        return trace.get_tracer(name, self.config.service_version)

    def get_meter(self, name: str):
        """Get a meter for the given module name."""
        from opentelemetry import metrics
        return metrics.get_meter(name, self.config.service_version)

    def shutdown(self):
        """Shutdown OTEL providers gracefully."""
        if not self._initialized:
            return

        logger.info("Shutting down OTEL providers...")

        if self._tracer_provider:
            self._tracer_provider.shutdown()

        if self._meter_provider:
            self._meter_provider.shutdown()

        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if OTEL is initialized."""
        return self._initialized


def get_provider() -> Optional[OTELProvider]:
    """Get the global OTEL provider instance."""
    return _provider


def set_provider(provider: OTELProvider):
    """Set the global OTEL provider instance."""
    global _provider
    _provider = provider


def reset_provider():
    """Reset the global provider (mainly for testing)."""
    global _provider
    if _provider and _provider.is_initialized:
        _provider.shutdown()
    _provider = None


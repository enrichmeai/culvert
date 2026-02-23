"""
OpenTelemetry configuration for pipeline observability.

Supports configuration via:
- Direct code configuration
- Environment variables
- Configuration files

Environment Variables:
    OTEL_SERVICE_NAME: Service name
    OTEL_EXPORTER_TYPE: Exporter type (console, otlp, dynatrace, gcp_trace, none)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint
    DYNATRACE_OTEL_URL: Dynatrace OTLP URL
    DYNATRACE_API_TOKEN: Dynatrace API token
    GCP_PROJECT_ID: GCP project ID
    OTEL_SAMPLE_RATE: Sampling rate (0.0 to 1.0)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
import os


class OTELExporterType(Enum):
    """Supported OTEL exporters."""
    CONSOLE = "console"      # Debug output to console
    OTLP = "otlp"           # Generic OTLP (gRPC)
    OTLP_HTTP = "otlp_http" # OTLP over HTTP (Dynatrace uses this)
    GCP_OTLP = "gcp_otlp"   # GCP Native OTel (telemetry.googleapis.com)
    GCP_TRACE = "gcp_trace" # Google Cloud Trace (Legacy/Direct)
    DYNATRACE = "dynatrace" # Dynatrace (convenience alias for OTLP_HTTP)
    NONE = "none"           # Disabled


def _get_exporter_type() -> OTELExporterType:
    """Get exporter type from environment, default to NONE."""
    env_value = os.getenv("OTEL_EXPORTER_TYPE", "none").lower()
    try:
        return OTELExporterType(env_value)
    except ValueError:
        return OTELExporterType.NONE


@dataclass
class OTELConfig:
    """
    Configuration for OpenTelemetry integration.

    Attributes:
        service_name: Name of the service (e.g., "application1-pipeline")
        service_version: Version of the service
        environment: Deployment environment (dev, staging, prod)
        exporter_type: Type of exporter to use
        otlp_endpoint: OTLP endpoint URL
        dynatrace_url: Dynatrace OTLP endpoint
        dynatrace_token: Dynatrace API token
        gcp_project_id: GCP project for Cloud Trace
        sample_rate: Trace sampling rate (0.0 to 1.0)
        batch_export: Whether to batch exports
        export_timeout_ms: Export timeout in milliseconds
        resource_attributes: Additional resource attributes

    Example:
        >>> config = OTELConfig.for_dynatrace(
        ...     service_name="application1-pipeline",
        ...     dynatrace_url="https://xyz.live.dynatrace.com/api/v2/otlp",
        ...     dynatrace_token="dt0c01.xxx",
        ... )
    """

    service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "gcp-pipeline")
    )
    service_version: str = "1.0.0"
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "dev")
    )

    # Exporter configuration
    exporter_type: OTELExporterType = field(default_factory=_get_exporter_type)

    # OTLP configuration
    otlp_endpoint: Optional[str] = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )

    # Dynatrace configuration
    dynatrace_url: Optional[str] = field(
        default_factory=lambda: os.getenv("DYNATRACE_OTEL_URL")
    )
    dynatrace_token: Optional[str] = field(
        default_factory=lambda: os.getenv("DYNATRACE_API_TOKEN")
    )

    # GCP configuration
    gcp_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID")
    )

    # Sampling and batching
    sample_rate: float = field(
        default_factory=lambda: float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))
    )
    batch_export: bool = True
    export_timeout_ms: int = 30000

    # Additional attributes
    resource_attributes: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if self.exporter_type == OTELExporterType.DYNATRACE:
            if not self.dynatrace_url:
                raise ValueError("dynatrace_url required for Dynatrace exporter")
            if not self.dynatrace_token:
                raise ValueError("dynatrace_token required for Dynatrace exporter")

        if self.exporter_type == OTELExporterType.OTLP and not self.otlp_endpoint:
            raise ValueError("otlp_endpoint required for OTLP exporter")

        if self.exporter_type == OTELExporterType.GCP_TRACE and not self.gcp_project_id:
            raise ValueError("gcp_project_id required for GCP Trace exporter")

    @classmethod
    def for_dynatrace(
        cls,
        service_name: str,
        dynatrace_url: str,
        dynatrace_token: str,
        environment: str = "dev",
        **kwargs
    ) -> "OTELConfig":
        """
        Create configuration for Dynatrace.

        Args:
            service_name: Name of the pipeline service
            dynatrace_url: Dynatrace OTLP endpoint
                Example: https://your-env.live.dynatrace.com/api/v2/otlp
            dynatrace_token: Dynatrace API token with otlp.ingest scope
            environment: Deployment environment

        Returns:
            Configured OTELConfig for Dynatrace
        """
        return cls(
            service_name=service_name,
            exporter_type=OTELExporterType.DYNATRACE,
            dynatrace_url=dynatrace_url,
            dynatrace_token=dynatrace_token,
            environment=environment,
            **kwargs
        )

    @classmethod
    def for_gcp_otlp(
        cls,
        service_name: str,
        project_id: str,
        environment: str = "dev",
        **kwargs
    ) -> "OTELConfig":
        """
        Create configuration for GCP native OTel ingestion.

        Args:
            service_name: Name of the pipeline service
            project_id: GCP project ID
            environment: Deployment environment

        Returns:
            Configured OTELConfig for GCP OTel (telemetry.googleapis.com)
        """
        return cls(
            service_name=service_name,
            exporter_type=OTELExporterType.GCP_OTLP,
            gcp_project_id=project_id,
            otlp_endpoint="telemetry.googleapis.com:443",
            environment=environment,
            **kwargs
        )

    @classmethod
    def for_gcp(
        cls,
        service_name: str,
        project_id: str,
        environment: str = "dev",
        **kwargs
    ) -> "OTELConfig":
        """
        Create configuration for Google Cloud Trace.

        Args:
            service_name: Name of the pipeline service
            project_id: GCP project ID
            environment: Deployment environment

        Returns:
            Configured OTELConfig for GCP Trace
        """
        return cls(
            service_name=service_name,
            exporter_type=OTELExporterType.GCP_TRACE,
            gcp_project_id=project_id,
            environment=environment,
            **kwargs
        )

    @classmethod
    def for_console(cls, service_name: str = "debug-pipeline") -> "OTELConfig":
        """Create configuration for console output (debugging)."""
        return cls(
            service_name=service_name,
            exporter_type=OTELExporterType.CONSOLE,
        )

    @classmethod
    def disabled(cls) -> "OTELConfig":
        """Create disabled configuration."""
        return cls(exporter_type=OTELExporterType.NONE)


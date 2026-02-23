"""Tests for OTEL provider and exporters."""

import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock the opentelemetry.exporter module before importing from it
mock_otlp_span = MagicMock()
mock_otlp_metric = MagicMock()
sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = MagicMock(OTLPSpanExporter=mock_otlp_span)
sys.modules["opentelemetry.exporter.otlp.proto.grpc.metric_exporter"] = MagicMock(OTLPMetricExporter=mock_otlp_metric)
sys.modules["opentelemetry.exporter.otlp.proto.http.trace_exporter"] = MagicMock()
sys.modules["opentelemetry.exporter.otlp.proto.http.metric_exporter"] = MagicMock()
sys.modules["opentelemetry.sdk.resources"] = MagicMock()

from gcp_pipeline_core.monitoring.otel import OTELConfig, OTELExporterType
from gcp_pipeline_core.monitoring.otel.provider import OTELProvider, reset_provider

class TestOTELProvider:
    """Tests for OTELProvider class."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        reset_provider()
        mock_otlp_span.reset_mock()
        mock_otlp_metric.reset_mock()

    def teardown_method(self):
        """Clean up after each test."""
        reset_provider()

    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.sdk.metrics.MeterProvider")
    def test_initialize_gcp_otlp(self, mock_meter_provider, mock_tracer_provider):
        """Test initialization with GCP OTLP exporter."""
        config = OTELConfig.for_gcp_otlp(
            service_name="test-service",
            project_id="test-project"
        )
        provider = OTELProvider(config)
        
        # We need to mock the resource creation too or it might fail on imports
        with patch("opentelemetry.sdk.resources.Resource.create"):
            success = provider.initialize()
            
            assert success is True
            assert provider.is_initialized is True
            
            # Verify exporters were created with correct endpoint
            mock_otlp_span.assert_called_once()
            args, kwargs = mock_otlp_span.call_args
            assert kwargs["endpoint"] == "telemetry.googleapis.com:443"
            
            mock_otlp_metric.assert_called_once()
            args, kwargs = mock_otlp_metric.call_args
            assert kwargs["endpoint"] == "telemetry.googleapis.com:443"

    def test_create_trace_exporter_gcp_otlp(self):
        """Test _create_trace_exporter for GCP_OTLP."""
        config = OTELConfig.for_gcp_otlp("test", "project")
        provider = OTELProvider(config)
        
        exporter = provider._create_trace_exporter()
        assert exporter is not None
        mock_otlp_span.assert_called_once_with(
            endpoint="telemetry.googleapis.com:443",
            timeout=30
        )

    def test_create_metrics_exporter_gcp_otlp(self):
        """Test _create_metrics_exporter for GCP_OTLP."""
        config = OTELConfig.for_gcp_otlp("test", "project")
        provider = OTELProvider(config)
        
        exporter = provider._create_metrics_exporter()
        assert exporter is not None
        mock_otlp_metric.assert_called_once_with(
            endpoint="telemetry.googleapis.com:443",
            timeout=30
        )

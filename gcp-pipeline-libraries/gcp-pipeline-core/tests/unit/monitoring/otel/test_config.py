"""Tests for OTEL configuration."""

import os
import pytest
from unittest.mock import patch

from gcp_pipeline_core.monitoring.otel import OTELConfig, OTELExporterType


class TestOTELExporterType:
    """Tests for OTELExporterType enum."""

    def test_all_exporter_types_exist(self):
        """Test all expected exporter types exist."""
        assert OTELExporterType.CONSOLE.value == "console"
        assert OTELExporterType.OTLP.value == "otlp"
        assert OTELExporterType.OTLP_HTTP.value == "otlp_http"
        assert OTELExporterType.GCP_TRACE.value == "gcp_trace"
        assert OTELExporterType.DYNATRACE.value == "dynatrace"
        assert OTELExporterType.NONE.value == "none"


class TestOTELConfig:
    """Tests for OTELConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = OTELConfig()
        assert config.service_name == "gcp-pipeline"
        assert config.exporter_type == OTELExporterType.NONE
        assert config.sample_rate == 1.0
        assert config.batch_export is True

    def test_default_service_version(self):
        """Test default service version."""
        config = OTELConfig()
        assert config.service_version == "1.0.0"

    def test_dynatrace_config_factory(self):
        """Test Dynatrace configuration factory."""
        config = OTELConfig.for_dynatrace(
            service_name="test-pipeline",
            dynatrace_url="https://test.dynatrace.com/api/v2/otlp",
            dynatrace_token="dt0c01.test",
        )
        assert config.exporter_type == OTELExporterType.DYNATRACE
        assert config.dynatrace_url == "https://test.dynatrace.com/api/v2/otlp"
        assert config.dynatrace_token == "dt0c01.test"
        assert config.service_name == "test-pipeline"

    def test_dynatrace_config_with_environment(self):
        """Test Dynatrace configuration with environment."""
        config = OTELConfig.for_dynatrace(
            service_name="test-pipeline",
            dynatrace_url="https://test.dynatrace.com/api/v2/otlp",
            dynatrace_token="dt0c01.test",
            environment="production",
        )
        assert config.environment == "production"

    def test_dynatrace_requires_url(self):
        """Test Dynatrace config requires URL."""
        with pytest.raises(ValueError, match="dynatrace_url required"):
            OTELConfig(
                exporter_type=OTELExporterType.DYNATRACE,
                dynatrace_token="token",
            )

    def test_dynatrace_requires_token(self):
        """Test Dynatrace config requires token."""
        with pytest.raises(ValueError, match="dynatrace_token required"):
            OTELConfig(
                exporter_type=OTELExporterType.DYNATRACE,
                dynatrace_url="https://test.dynatrace.com",
            )

    def test_gcp_config_factory(self):
        """Test GCP Trace configuration factory."""
        config = OTELConfig.for_gcp(
            service_name="test-pipeline",
            project_id="my-project",
        )
        assert config.exporter_type == OTELExporterType.GCP_TRACE
        assert config.gcp_project_id == "my-project"
        assert config.service_name == "test-pipeline"

    def test_gcp_requires_project_id(self):
        """Test GCP Trace config requires project ID."""
        with pytest.raises(ValueError, match="gcp_project_id required"):
            OTELConfig(exporter_type=OTELExporterType.GCP_TRACE)

    def test_console_config_factory(self):
        """Test console configuration factory."""
        config = OTELConfig.for_console()
        assert config.exporter_type == OTELExporterType.CONSOLE
        assert config.service_name == "debug-pipeline"

    def test_console_config_with_custom_name(self):
        """Test console configuration with custom service name."""
        config = OTELConfig.for_console(service_name="my-debug")
        assert config.service_name == "my-debug"

    def test_disabled_config_factory(self):
        """Test disabled configuration factory."""
        config = OTELConfig.disabled()
        assert config.exporter_type == OTELExporterType.NONE

    def test_otlp_requires_endpoint(self):
        """Test OTLP config requires endpoint."""
        with pytest.raises(ValueError, match="otlp_endpoint required"):
            OTELConfig(exporter_type=OTELExporterType.OTLP)

    def test_otlp_with_endpoint(self):
        """Test OTLP config with endpoint."""
        config = OTELConfig(
            exporter_type=OTELExporterType.OTLP,
            otlp_endpoint="http://localhost:4317",
        )
        assert config.otlp_endpoint == "http://localhost:4317"

    def test_resource_attributes(self):
        """Test resource attributes."""
        config = OTELConfig(
            resource_attributes={"custom.key": "custom.value"}
        )
        assert config.resource_attributes["custom.key"] == "custom.value"

    @patch.dict(os.environ, {"OTEL_SERVICE_NAME": "env-service"})
    def test_service_name_from_env(self):
        """Test service name from environment variable."""
        config = OTELConfig()
        assert config.service_name == "env-service"

    @patch.dict(os.environ, {"DYNATRACE_OTEL_URL": "https://env.dynatrace.com"})
    def test_dynatrace_url_from_env(self):
        """Test Dynatrace URL from environment variable."""
        config = OTELConfig()
        assert config.dynatrace_url == "https://env.dynatrace.com"

    @patch.dict(os.environ, {"GCP_PROJECT_ID": "env-project"})
    def test_gcp_project_from_env(self):
        """Test GCP project from environment variable."""
        config = OTELConfig()
        assert config.gcp_project_id == "env-project"

    @patch.dict(os.environ, {"OTEL_SAMPLE_RATE": "0.5"})
    def test_sample_rate_from_env(self):
        """Test sample rate from environment variable."""
        config = OTELConfig()
        assert config.sample_rate == 0.5

    @patch.dict(os.environ, {"ENVIRONMENT": "staging"})
    def test_environment_from_env(self):
        """Test environment from environment variable."""
        config = OTELConfig()
        assert config.environment == "staging"


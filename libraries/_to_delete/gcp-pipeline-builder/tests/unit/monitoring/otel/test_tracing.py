"""Tests for OTEL tracing utilities."""

import pytest
from unittest.mock import MagicMock, patch

from gcp_pipeline_builder.monitoring.otel import (
    OTELConfig,
    configure_otel,
    is_otel_initialized,
    get_tracer,
    get_meter,
    shutdown_otel,
    trace_function,
)
from gcp_pipeline_builder.monitoring.otel.provider import reset_provider


class TestConfigureOtel:
    """Tests for configure_otel function."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        shutdown_otel()
        reset_provider()

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_otel()
        reset_provider()

    def test_configure_disabled(self):
        """Test configuring OTEL with disabled config."""
        config = OTELConfig.disabled()
        result = configure_otel(config)
        assert result is False
        assert is_otel_initialized() is False

    def test_is_otel_initialized_initially_false(self):
        """Test OTEL is not initialized by default."""
        assert is_otel_initialized() is False


class TestGetTracer:
    """Tests for get_tracer function."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        shutdown_otel()
        reset_provider()

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_otel()
        reset_provider()

    def test_get_tracer_returns_noop_when_not_initialized(self):
        """Test get_tracer returns no-op tracer when not initialized."""
        tracer = get_tracer("test_module")
        assert tracer is not None
        # Should be able to create spans without error
        with tracer.start_as_current_span("test") as span:
            pass  # Should not raise

    def test_get_tracer_with_name(self):
        """Test get_tracer with custom name."""
        tracer = get_tracer("my_custom_module")
        assert tracer is not None


class TestGetMeter:
    """Tests for get_meter function."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        shutdown_otel()
        reset_provider()

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_otel()
        reset_provider()

    def test_get_meter_returns_noop_when_not_initialized(self):
        """Test get_meter returns no-op meter when not initialized."""
        meter = get_meter("test_module")
        assert meter is not None

    def test_create_counter_on_noop_meter(self):
        """Test creating counter on no-op meter."""
        meter = get_meter("test_module")
        counter = meter.create_counter("test_counter")
        # Should be able to add without error
        counter.add(1)


class TestTraceFunction:
    """Tests for trace_function decorator."""

    def test_trace_function_executes_function(self):
        """Test decorated function executes correctly."""
        @trace_function()
        def my_function(x, y):
            return x + y

        result = my_function(2, 3)
        assert result == 5

    def test_trace_function_with_custom_name(self):
        """Test decorated function with custom span name."""
        @trace_function(span_name="custom_operation")
        def my_function():
            return "done"

        result = my_function()
        assert result == "done"

    def test_trace_function_with_attributes(self):
        """Test decorated function with attributes."""
        @trace_function(attributes={"component": "test"})
        def my_function():
            return "done"

        result = my_function()
        assert result == "done"

    def test_trace_function_propagates_exception(self):
        """Test decorated function propagates exceptions."""
        @trace_function()
        def my_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            my_function()

    def test_trace_function_preserves_return_value(self):
        """Test decorated function preserves return value."""
        @trace_function()
        def my_function():
            return {"key": "value"}

        result = my_function()
        assert result == {"key": "value"}

    def test_trace_function_with_kwargs(self):
        """Test decorated function with kwargs."""
        @trace_function()
        def my_function(a, b=10):
            return a + b

        result = my_function(5, b=20)
        assert result == 25


class TestShutdownOtel:
    """Tests for shutdown_otel function."""

    def test_shutdown_when_not_initialized(self):
        """Test shutdown when OTEL is not initialized."""
        # Should not raise
        shutdown_otel()
        assert is_otel_initialized() is False


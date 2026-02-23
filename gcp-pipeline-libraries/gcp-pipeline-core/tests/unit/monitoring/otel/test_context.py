"""Tests for OTEL context management."""

import pytest
from unittest.mock import MagicMock, patch

from gcp_pipeline_core.monitoring.otel import OTELContext, SpanContext
from gcp_pipeline_core.monitoring.otel.tracing import shutdown_otel
from gcp_pipeline_core.monitoring.otel.provider import reset_provider


class TestSpanContext:
    """Tests for SpanContext wrapper."""

    def test_set_attribute_with_none_span(self):
        """Test set_attribute with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.set_attribute("key", "value")  # Should not raise

    def test_set_attributes_with_none_span(self):
        """Test set_attributes with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.set_attributes({"key1": "value1", "key2": "value2"})

    def test_add_event_with_none_span(self):
        """Test add_event with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.add_event("test_event", {"attr": "value"})

    def test_record_exception_with_none_span(self):
        """Test record_exception with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.record_exception(ValueError("test"))

    def test_set_status_ok_with_none_span(self):
        """Test set_status_ok with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.set_status_ok()

    def test_set_status_error_with_none_span(self):
        """Test set_status_error with None span doesn't raise."""
        ctx = SpanContext(None)
        ctx.set_status_error("error message")

    def test_set_attribute_with_mock_span(self):
        """Test set_attribute with mock span."""
        mock_span = MagicMock()
        ctx = SpanContext(mock_span)
        ctx.set_attribute("key", "value")
        mock_span.set_attribute.assert_called_once_with("key", "value")

    def test_set_attributes_with_mock_span(self):
        """Test set_attributes with mock span."""
        mock_span = MagicMock()
        ctx = SpanContext(mock_span)
        ctx.set_attributes({"key1": "value1", "key2": "value2"})
        assert mock_span.set_attribute.call_count == 2


class TestOTELContext:
    """Tests for OTELContext context manager."""

    def setup_method(self):
        """Reset OTEL state before each test."""
        shutdown_otel()
        reset_provider()

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_otel()
        reset_provider()

    def test_context_manager_enters_and_exits(self):
        """Test context manager enters and exits cleanly."""
        with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
            assert ctx is not None
            assert ctx.run_id == "run_123"
            assert ctx.systapplication1_id == "Application1"

    def test_context_with_entity_type(self):
        """Test context with entity type."""
        with OTELContext(
            run_id="run_123",
            systapplication1_id="Application1",
            entity_type="customers"
        ) as ctx:
            assert ctx.entity_type == "customers"

    def test_nested_span_creation(self):
        """Test nested span creation doesn't raise."""
        with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
            with ctx.span("validation") as span:
                span.set_attribute("records", 100)
            with ctx.span("transformation") as span:
                span.set_attribute("records", 100)

    def test_span_with_attributes(self):
        """Test span creation with custom attributes."""
        with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
            with ctx.span("operation", attributes={"custom": "value"}) as span:
                assert span is not None

    def test_exception_in_context(self):
        """Test exception handling in context."""
        with pytest.raises(ValueError, match="test error"):
            with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
                raise ValueError("test error")

    def test_exception_in_span(self):
        """Test exception handling in span."""
        with pytest.raises(ValueError, match="span error"):
            with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
                with ctx.span("operation") as span:
                    raise ValueError("span error")

    def test_base_attributes_set(self):
        """Test base attributes are set correctly."""
        with OTELContext(run_id="run_123", systapplication1_id="Application1") as ctx:
            assert ctx._base_attributes["run_id"] == "run_123"
            assert ctx._base_attributes["systapplication1_id"] == "Application1"

    def test_base_attributes_with_entity(self):
        """Test base attributes include entity type."""
        with OTELContext(
            run_id="run_123",
            systapplication1_id="Application1",
            entity_type="customers"
        ) as ctx:
            assert ctx._base_attributes["entity_type"] == "customers"

    def test_custom_tracer_name(self):
        """Test custom tracer name."""
        ctx = OTELContext(
            run_id="run_123",
            systapplication1_id="Application1",
            tracer_name="custom_tracer"
        )
        assert ctx._tracer is not None


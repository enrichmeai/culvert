"""
Context management for OTEL tracing.

Provides span context propagation and pipeline context tracking.
"""

from contextlib import contextmanager
from typing import Dict, Any, Optional
from .tracing import get_tracer
from ...utilities.logging import get_logger

logger = get_logger(__name__)


class SpanContext:
    """
    Wrapper for managing span lifecycle and attributes.

    Example:
        >>> with OTELContext(...) as ctx:
        ...     with ctx.span("validation") as span:
        ...         span.set_attribute("records", 1000)
    """

    def __init__(self, span):
        self._span = span

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        if self._span:
            try:
                self._span.set_attribute(key, value)
            except Exception as e:
                logger.debug(f"Failed to set span attribute {key}: {e}")

    def set_attributes(self, attributes: Dict[str, Any]):
        """Set multiple span attributes."""
        if self._span:
            for key, value in attributes.items():
                self.set_attribute(key, value)

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span."""
        if self._span:
            try:
                self._span.add_event(name, attributes)
            except Exception as e:
                logger.debug(f"Failed to add span event {name}: {e}")

    def record_exception(self, exception: Exception):
        """Record an exception on the span."""
        if self._span:
            try:
                self._span.record_exception(exception)
            except Exception as e:
                logger.debug(f"Failed to record exception on span: {e}")

    def set_status_ok(self):
        """Set span status to OK."""
        if self._span:
            try:
                from opentelemetry.trace import StatusCode
                self._span.set_status(StatusCode.OK)
            except Exception as e:
                logger.debug(f"Failed to set span status OK: {e}")

    def set_status_error(self, message: str = ""):
        """Set span status to ERROR."""
        if self._span:
            try:
                from opentelemetry.trace import StatusCode
                self._span.set_status(StatusCode.ERROR, message)
            except Exception as e:
                logger.debug(f"Failed to set span status ERROR: {e}")


class OTELContext:
    """
    High-level context manager for pipeline tracing.

    Provides a consistent interface for tracing pipeline stages
    with automatic attribute injection.

    Example:
        >>> with OTELContext(
        ...     run_id="application1_20260105_143022",
        ...     systapplication1_id="Application1",
        ...     entity_type="customers"
        ... ) as ctx:
        ...     with ctx.span("validation") as span:
        ...         span.set_attribute("records", 1000)
        ...         validate_records()
        ...     with ctx.span("transformation") as span:
        ...         transform_records()
    """

    def __init__(
        self,
        run_id: str,
        systapplication1_id: str,
        entity_type: Optional[str] = None,
        tracer_name: str = "pipeline",
    ):
        self.run_id = run_id
        self.systapplication1_id = systapplication1_id
        self.entity_type = entity_type
        self._tracer = get_tracer(tracer_name)
        self._root_span = None
        self._base_attributes = {
            "run_id": run_id,
            "systapplication1_id": systapplication1_id,
        }
        if entity_type:
            self._base_attributes["entity_type"] = entity_type

    def __enter__(self):
        """Start root span for the pipeline context."""
        try:
            span_name = f"{self.systapplication1_id}_pipeline"
            if self.entity_type:
                span_name = f"{span_name}_{self.entity_type}"

            self._root_span = self._tracer.start_span(span_name)
            for key, value in self._base_attributes.items():
                self._root_span.set_attribute(key, value)
        except Exception as e:
            logger.debug(f"Failed to start root span: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End root span."""
        if self._root_span:
            try:
                if exc_type:
                    self._root_span.record_exception(exc_val)
                    from opentelemetry.trace import StatusCode
                    self._root_span.set_status(StatusCode.ERROR, str(exc_val))
                else:
                    from opentelemetry.trace import StatusCode
                    self._root_span.set_status(StatusCode.OK)
                self._root_span.end()
            except Exception as e:
                logger.debug(f"Failed to end root span: {e}")

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a child span within this context.

        Args:
            name: Span name
            attributes: Additional attributes

        Yields:
            SpanContext for the created span
        """
        span = None
        try:
            span = self._tracer.start_span(
                name,
                context=self._get_context(),
            )

            # Add base attributes
            for key, value in self._base_attributes.items():
                span.set_attribute(key, value)

            # Add custom attributes
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
        except Exception as e:
            logger.debug(f"Failed to start span {name}: {e}")

        try:
            yield SpanContext(span)
            if span:
                try:
                    from opentelemetry.trace import StatusCode
                    span.set_status(StatusCode.OK)
                except Exception as e:
                    logger.debug(f"Failed to set span status OK: {e}")
        except Exception as e:
            if span:
                try:
                    from opentelemetry.trace import StatusCode
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, str(e))
                except Exception as ex:
                    logger.debug(f"Failed to set span status ERROR: {ex}")
            raise
        finally:
            if span:
                try:
                    span.end()
                except Exception as e:
                    logger.debug(f"Failed to end span: {e}")

    def _get_context(self):
        """Get current trace context."""
        try:
            from opentelemetry import context
            return context.get_current()
        except Exception as e:
            logger.debug(f"Failed to get current context: {e}")
            return None


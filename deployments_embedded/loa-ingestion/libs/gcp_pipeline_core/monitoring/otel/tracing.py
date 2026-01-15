"""
Tracing utilities and decorators for pipeline instrumentation.

Provides:
- Function decorators for automatic tracing
- Beam DoFn tracing support
- Context propagation utilities
"""

import functools
import logging
from typing import Callable, Optional, Any, Dict

from .config import OTELConfig
from .provider import OTELProvider, get_provider, set_provider, reset_provider

logger = logging.getLogger(__name__)

# Global state
_initialized = False


def configure_otel(config: OTELConfig) -> bool:
    """
    Configure and initialize OpenTelemetry.

    This should be called once at application startup.

    Args:
        config: OTEL configuration

    Returns:
        True if initialization successful

    Example:
        >>> config = OTELConfig.for_dynatrace(
        ...     service_name="em-pipeline",
        ...     dynatrace_url="https://xyz.live.dynatrace.com/api/v2/otlp",
        ...     dynatrace_token="dt0c01.xxx",
        ... )
        >>> configure_otel(config)
        True
    """
    global _initialized

    if _initialized:
        logger.warning("OTEL already configured")
        return True

    provider = OTELProvider(config)
    success = provider.initialize()

    if success:
        set_provider(provider)
        _initialized = True

    return success


def is_otel_initialized() -> bool:
    """Check if OTEL has been initialized."""
    return _initialized


def get_tracer(name: str = __name__):
    """
    Get a tracer for creating spans.

    Args:
        name: Module or component name

    Returns:
        OTEL Tracer or NoOp tracer if not initialized

    Example:
        >>> tracer = get_tracer("my_module")
        >>> with tracer.start_as_current_span("process") as span:
        ...     span.set_attribute("records", 100)
        ...     do_work()
    """
    provider = get_provider()
    if provider and provider.is_initialized:
        return provider.get_tracer(name)

    # Return a no-op tracer
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


def get_meter(name: str = __name__):
    """
    Get a meter for creating metrics.

    Args:
        name: Module or component name

    Returns:
        OTEL Meter or NoOp meter if not initialized

    Example:
        >>> meter = get_meter("my_module")
        >>> counter = meter.create_counter("records_processed")
        >>> counter.add(100, {"entity": "customers"})
    """
    provider = get_provider()
    if provider and provider.is_initialized:
        return provider.get_meter(name)

    # Return a no-op meter
    try:
        from opentelemetry import metrics
        return metrics.get_meter(name)
    except ImportError:
        return _NoOpMeter()


def get_logger_provider():
    """Get the logger provider (for future log correlation)."""
    # TODO: Implement log correlation when OTEL logging is stable
    return None


def shutdown_otel():
    """Shutdown OTEL gracefully."""
    global _initialized
    provider = get_provider()
    if provider:
        provider.shutdown()
    reset_provider()
    _initialized = False


def trace_function(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
):
    """
    Decorator to trace a function execution.

    Args:
        span_name: Name of the span (defaults to function name)
        attributes: Static attributes to add to span
        record_exception: Whether to record exceptions

    Example:
        >>> @trace_function(attributes={"component": "validation"})
        ... def validate_record(record):
        ...     return True
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            name = span_name or func.__name__

            try:
                with tracer.start_as_current_span(name) as span:
                    # Add static attributes
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                    # Add function info
                    span.set_attribute("code.function", func.__name__)
                    span.set_attribute("code.namespace", func.__module__)

                    try:
                        result = func(*args, **kwargs)
                        span.set_attribute("status", "success")
                        return result
                    except Exception as e:
                        span.set_attribute("status", "error")
                        if record_exception:
                            span.record_exception(e)
                        raise
            except Exception:
                # If OTEL is not available, just run the function
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_beam_dofn(dofn_class):
    """
    Class decorator to add tracing to Apache Beam DoFn.

    Wraps the process method to create spans for each element processed.

    Example:
        >>> @trace_beam_dofn
        ... class MyDoFn(beam.DoFn):
        ...     def process(self, element):
        ...         yield element
    """
    original_process = dofn_class.process

    @functools.wraps(original_process)
    def traced_process(self, element, *args, **kwargs):
        tracer = get_tracer(dofn_class.__module__)
        span_name = f"{dofn_class.__name__}.process"

        try:
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("beam.dofn", dofn_class.__name__)

                try:
                    for output in original_process(self, element, *args, **kwargs):
                        yield output
                    span.set_attribute("status", "success")
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.record_exception(e)
                    raise
        except Exception:
            # If OTEL fails, just run the original process
            for output in original_process(self, element, *args, **kwargs):
                yield output

    dofn_class.process = traced_process
    return dofn_class


class _NoOpSpan:
    """No-op span for when OTEL is not available."""

    def set_attribute(self, key: str, value: Any):
        pass

    def set_attributes(self, attributes: Dict[str, Any]):
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        pass

    def record_exception(self, exception: Exception):
        pass

    def set_status(self, status, description: str = ""):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class _NoOpTracer:
    """No-op tracer for when OTEL is not available."""

    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()


class _NoOpMeter:
    """No-op meter for when OTEL is not available."""

    def create_counter(self, name: str, **kwargs):
        return _NoOpCounter()

    def create_up_down_counter(self, name: str, **kwargs):
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs):
        return _NoOpHistogram()


class _NoOpCounter:
    """No-op counter for when OTEL is not available."""

    def add(self, value: int, attributes: Optional[Dict[str, str]] = None):
        pass


class _NoOpHistogram:
    """No-op histogram for when OTEL is not available."""

    def record(self, value: float, attributes: Optional[Dict[str, str]] = None):
        pass


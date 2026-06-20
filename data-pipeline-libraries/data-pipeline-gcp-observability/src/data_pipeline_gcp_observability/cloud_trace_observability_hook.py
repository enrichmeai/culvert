"""CloudTraceObservabilityHook — ObservabilityHook backed by OpenTelemetry.

Java sibling:
  data-pipeline-libraries-java/data-pipeline-gcp-observability-java/src/main/java/
  com/enrichmeai/culvert/gcp/observability/CloudTraceObservabilityHook.java

The OTel SDK and exporter are injected by the caller; this class only wraps
them as the Culvert ObservabilityHook Protocol surface.  All SDK imports are
performed lazily so the module can be imported even when the OTel SDK is not
installed (e.g. in unit test environments that only install mocks).

Sprint-19 / T19.2 — issue #125.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Mapping

logger = logging.getLogger(__name__)

# Sentinel for empty tag mappings — avoids dict construction on every call.
_NO_TAGS: Mapping[str, str] = {}


class CloudTraceObservabilityHook:
    """ObservabilityHook implementation backed by OpenTelemetry.

    Mirrors Java ``CloudTraceObservabilityHook`` (file line 71).

    Callers construct an OpenTelemetry instance whose tracer / meter providers
    export to Google Cloud Trace / Cloud Monitoring and pass it here.  This
    class only wraps the resulting tracer and meter and bridges them to the
    Culvert ``ObservabilityHook`` Protocol.

    Construction
    ------------
    - ``CloudTraceObservabilityHook(tracer, meter)`` — primary; inject
      already-resolved tracer and meter (OTel SDK objects or mocks).
    - ``CloudTraceObservabilityHook.from_otel(otel, scope)`` — convenience
      class-method; mirrors Java ``(OpenTelemetry, String)`` constructor
      (line 127).  Requires the OTel SDK to be installed.
    - ``CloudTraceObservabilityHook()`` — no-arg; wraps the OTel global SDK
      (mirrors Java no-arg ctor, line 113).  Requires the OTel SDK.

    The no-arg and ``from_otel`` paths perform lazy SDK imports so that the
    class can be imported even when the SDK is absent.

    Instrument caches (counters, histograms) are ``dict``-backed; OTel
    instruments are keyed by name so re-registration is avoided, mirroring
    Java ``ConcurrentHashMap`` caches (line 91–93).
    """

    DEFAULT_INSTRUMENTATION_SCOPE = "com.enrichmeai.culvert"

    def __init__(self, tracer: Any, meter: Any) -> None:
        """Inject an already-resolved OTel tracer and meter.

        Both are required.  Pass ``MagicMock()`` instances in tests.

        Args:
            tracer: OTel Tracer (or mock).
            meter:  OTel Meter (or mock).

        Raises:
            TypeError: if either argument is None.
        """
        if tracer is None:
            raise TypeError("tracer must not be None")
        if meter is None:
            raise TypeError("meter must not be None")
        self._tracer = tracer
        self._meter = meter
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}

    @classmethod
    def from_otel(cls, otel: Any, scope: str) -> "CloudTraceObservabilityHook":
        """Build from an ``OpenTelemetry`` instance and an instrumentation scope.

        Mirrors Java primary constructor (line 127).

        Args:
            otel:  Configured OpenTelemetry instance.
            scope: Instrumentation scope name (typically the pipeline name).

        Raises:
            TypeError:     if either argument is None.
            ImportError:   if ``opentelemetry-api`` is not installed.
        """
        if otel is None:
            raise TypeError("otel must not be None")
        if scope is None:
            raise TypeError("scope must not be None")
        return cls(otel.get_tracer(scope), otel.get_meter(scope))

    @classmethod
    def default(cls) -> "CloudTraceObservabilityHook":
        """Build from the OTel global SDK.

        Mirrors Java no-arg constructor (line 113).

        Raises:
            ImportError: if ``opentelemetry-api`` is not installed.
        """
        try:
            from opentelemetry import trace, metrics  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "opentelemetry-api is required for CloudTraceObservabilityHook.default(). "
                "Install it with: pip install opentelemetry-api"
            ) from exc
        tracer = trace.get_tracer(cls.DEFAULT_INSTRUMENTATION_SCOPE)
        meter = metrics.get_meter(cls.DEFAULT_INSTRUMENTATION_SCOPE)
        return cls(tracer, meter)

    # ------------------------------------------------------------------
    # ObservabilityHook Protocol
    # ------------------------------------------------------------------

    def counter(
        self,
        name: str,
        value: int = 1,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Increment a monotonic counter — mirrors Java counter() (line 146)."""
        if name is None:
            raise TypeError("name must not be None")
        instrument = self._counters.get(name)
        if instrument is None:
            instrument = self._meter.create_counter(name)
            self._counters[name] = instrument
        instrument.add(value, self._to_attributes(tags))

    def gauge(
        self,
        name: str,
        value: float,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Record a gauge value — mirrors Java gauge() (line 153)."""
        if name is None:
            raise TypeError("name must not be None")
        instrument = self._gauges.get(name)
        if instrument is None:
            # Use histogram as a gauge proxy (mirrors Java comment, line 158).
            instrument = self._meter.create_histogram(name)
            self._gauges[name] = instrument
        instrument.record(value, self._to_attributes(tags))

    def histogram(
        self,
        name: str,
        value: float,
        tags: Mapping[str, str] = _NO_TAGS,
    ) -> None:
        """Record a histogram observation — mirrors Java histogram() (line 166)."""
        if name is None:
            raise TypeError("name must not be None")
        instrument = self._histograms.get(name)
        if instrument is None:
            instrument = self._meter.create_histogram(name)
            self._histograms[name] = instrument
        instrument.record(value, self._to_attributes(tags))

    def log(self, level: str, message: str, **fields: Any) -> None:
        """Structured log — mirrors Java log() (line 174).

        ``level`` is mapped to the stdlib logging level (DEBUG/INFO/WARNING/ERROR).
        ``**fields`` are appended as ``key=value`` pairs on the log message,
        mirroring the Java ``renderFields`` helper (line 211).
        """
        if level is None:
            raise TypeError("level must not be None")
        if message is None:
            raise TypeError("message must not be None")
        rendered = self._render_fields(message, fields)
        upper = level.upper()
        if upper == "DEBUG":
            logger.debug(rendered)
        elif upper in ("WARNING", "WARN"):
            logger.warning(rendered)
        elif upper == "ERROR":
            logger.error(rendered)
        elif upper == "CRITICAL":
            logger.critical(rendered)
        else:
            logger.info(rendered)

    @contextmanager
    def span(self, name: str) -> Generator[Any, None, None]:
        """Open a tracing span — mirrors Java span() + OtelSpanAdapter (line 189, 234).

        Uses the injected tracer.  If the tracer is a mock the context manager
        still works because we guard every OTel call.

        Yields the underlying span object (or mock).
        """
        if name is None:
            raise TypeError("name must not be None")
        otel_span = self._tracer.start_span(name)
        try:
            yield otel_span
        except Exception as exc:
            try:
                otel_span.record_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            try:
                otel_span.end()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_attributes(tags: Mapping[str, str]) -> dict[str, str]:
        """Convert a tags mapping to a plain dict (OTel attribute map)."""
        if not tags:
            return {}
        return {k: v for k, v in tags.items() if k is not None and v is not None}

    @staticmethod
    def _render_fields(message: str, fields: dict[str, Any]) -> str:
        """Append ``key=value`` pairs to ``message`` — mirrors Java renderFields (line 211)."""
        if not fields:
            return message
        parts = " ".join(f"{k}={v}" for k, v in fields.items())
        return f"{message} {parts}"

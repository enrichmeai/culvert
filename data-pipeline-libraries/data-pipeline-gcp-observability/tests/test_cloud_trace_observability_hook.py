"""Tests for CloudTraceObservabilityHook — GCP/OTel clients are mocked.

All SDK imports are avoided; the hook is exercised with MagicMock tracer/meter.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from data_pipeline_gcp_observability import CloudTraceObservabilityHook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_tracer():
    tracer = MagicMock()
    # start_span returns an object with .end() and .record_exception()
    span = MagicMock()
    tracer.start_span.return_value = span
    return tracer


@pytest.fixture
def mock_meter():
    meter = MagicMock()
    counter = MagicMock()
    histogram = MagicMock()
    meter.create_counter.return_value = counter
    meter.create_histogram.return_value = histogram
    return meter


@pytest.fixture
def hook(mock_tracer, mock_meter):
    return CloudTraceObservabilityHook(mock_tracer, mock_meter)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_rejects_none_tracer(self, mock_meter):
        with pytest.raises(TypeError):
            CloudTraceObservabilityHook(None, mock_meter)

    def test_rejects_none_meter(self, mock_tracer):
        with pytest.raises(TypeError):
            CloudTraceObservabilityHook(mock_tracer, None)

    def test_accepts_valid_args(self, mock_tracer, mock_meter):
        h = CloudTraceObservabilityHook(mock_tracer, mock_meter)
        assert h is not None

    def test_from_otel_rejects_none_otel(self):
        with pytest.raises(TypeError):
            CloudTraceObservabilityHook.from_otel(None, "scope")

    def test_from_otel_rejects_none_scope(self):
        otel = MagicMock()
        with pytest.raises(TypeError):
            CloudTraceObservabilityHook.from_otel(otel, None)

    def test_from_otel_builds_hook(self):
        otel = MagicMock()
        h = CloudTraceObservabilityHook.from_otel(otel, "my-pipeline")
        assert h is not None
        otel.get_tracer.assert_called_once_with("my-pipeline")
        otel.get_meter.assert_called_once_with("my-pipeline")

    def test_default_scope_constant(self):
        assert CloudTraceObservabilityHook.DEFAULT_INSTRUMENTATION_SCOPE == "com.enrichmeai.culvert"


# ---------------------------------------------------------------------------
# counter()
# ---------------------------------------------------------------------------

class TestCounter:
    def test_counter_creates_instrument_and_adds(self, hook, mock_meter):
        hook.counter("my.counter", 3, {"env": "test"})
        mock_meter.create_counter.assert_called_once_with("my.counter")
        counter_inst = mock_meter.create_counter.return_value
        counter_inst.add.assert_called_once()
        args = counter_inst.add.call_args
        assert args[0][0] == 3

    def test_counter_default_value(self, hook, mock_meter):
        hook.counter("c")
        counter_inst = mock_meter.create_counter.return_value
        args = counter_inst.add.call_args
        assert args[0][0] == 1

    def test_counter_caches_instrument(self, hook, mock_meter):
        hook.counter("c")
        hook.counter("c")
        mock_meter.create_counter.assert_called_once()

    def test_counter_rejects_none_name(self, hook):
        with pytest.raises(TypeError):
            hook.counter(None)

    def test_counter_empty_tags(self, hook, mock_meter):
        hook.counter("c", tags={})
        counter_inst = mock_meter.create_counter.return_value
        _, kwargs = counter_inst.add.call_args
        # tags kwarg may be positional; just check it was called
        assert counter_inst.add.called


# ---------------------------------------------------------------------------
# gauge()
# ---------------------------------------------------------------------------

class TestGauge:
    def test_gauge_records_via_histogram(self, hook, mock_meter):
        hook.gauge("my.gauge", 42.5)
        mock_meter.create_histogram.assert_called_with("my.gauge")
        hist = mock_meter.create_histogram.return_value
        hist.record.assert_called_once()
        args = hist.record.call_args
        assert args[0][0] == 42.5

    def test_gauge_rejects_none_name(self, hook):
        with pytest.raises(TypeError):
            hook.gauge(None, 1.0)


# ---------------------------------------------------------------------------
# histogram()
# ---------------------------------------------------------------------------

class TestHistogram:
    def test_histogram_records_value(self, hook, mock_meter):
        hook.histogram("latency_ms", 99.0)
        hist = mock_meter.create_histogram.return_value
        hist.record.assert_called_once()

    def test_histogram_caches_instrument(self, hook, mock_meter):
        hook.histogram("h", 1.0)
        hook.histogram("h", 2.0)
        mock_meter.create_histogram.assert_called_once()

    def test_histogram_rejects_none_name(self, hook):
        with pytest.raises(TypeError):
            hook.histogram(None, 1.0)


# ---------------------------------------------------------------------------
# log()
# ---------------------------------------------------------------------------

class TestLog:
    def test_log_info(self, hook, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            hook.log("INFO", "hello")
        assert "hello" in caplog.text

    def test_log_debug(self, hook, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            hook.log("DEBUG", "dbg msg")
        assert "dbg msg" in caplog.text

    def test_log_warning(self, hook, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            hook.log("WARNING", "warn msg")
        assert "warn msg" in caplog.text

    def test_log_error(self, hook, caplog):
        import logging
        with caplog.at_level(logging.ERROR):
            hook.log("ERROR", "err msg")
        assert "err msg" in caplog.text

    def test_log_renders_fields(self, hook, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            hook.log("INFO", "base", run_id="r1", stage="s1")
        assert "run_id=r1" in caplog.text
        assert "stage=s1" in caplog.text

    def test_log_rejects_none_level(self, hook):
        with pytest.raises(TypeError):
            hook.log(None, "msg")

    def test_log_rejects_none_message(self, hook):
        with pytest.raises(TypeError):
            hook.log("INFO", None)

    def test_log_unknown_level_falls_back_to_info(self, hook, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            hook.log("VERBOSE", "verbose msg")
        assert "verbose msg" in caplog.text

    def test_log_warn_alias(self, hook, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            hook.log("WARN", "warn-alias")
        assert "warn-alias" in caplog.text


# ---------------------------------------------------------------------------
# span()
# ---------------------------------------------------------------------------

class TestSpan:
    def test_span_context_manager_calls_start_and_end(self, hook, mock_tracer):
        span_mock = mock_tracer.start_span.return_value
        with hook.span("my-span"):
            mock_tracer.start_span.assert_called_with("my-span")
        span_mock.end.assert_called_once()

    def test_span_records_exception_on_error(self, hook, mock_tracer):
        span_mock = mock_tracer.start_span.return_value
        with pytest.raises(ValueError):
            with hook.span("bad-span"):
                raise ValueError("oops")
        span_mock.record_exception.assert_called_once()
        span_mock.end.assert_called_once()

    def test_span_rejects_none_name(self, hook):
        with pytest.raises(TypeError):
            with hook.span(None):
                pass

    def test_span_end_called_even_if_record_exception_fails(self, hook, mock_tracer):
        span_mock = mock_tracer.start_span.return_value
        span_mock.record_exception.side_effect = RuntimeError("internal")
        with pytest.raises(ValueError):
            with hook.span("s"):
                raise ValueError("orig")
        span_mock.end.assert_called_once()

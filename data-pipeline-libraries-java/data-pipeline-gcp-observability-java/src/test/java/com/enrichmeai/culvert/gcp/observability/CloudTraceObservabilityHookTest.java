package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.DoubleHistogramBuilder;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.LongCounterBuilder;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link CloudTraceObservabilityHook}. Mocks the OTel
 * {@link Tracer} / {@link Meter} surface so no real Cloud Trace endpoint or
 * credentials are required.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class CloudTraceObservabilityHookTest {

    @Mock
    private Tracer tracer;
    @Mock
    private Meter meter;
    @Mock
    private SpanBuilder spanBuilder;
    @Mock
    private Span otelSpan;
    @Mock
    private Scope scope;
    @Mock
    private LongCounterBuilder counterBuilder;
    @Mock
    private LongCounter counter;
    @Mock
    private DoubleHistogramBuilder histogramBuilder;
    @Mock
    private DoubleHistogram histogram;

    // --- span lifecycle ----------------------------------------------------

    @Test
    void spanStartReturnsAdapterThatEndsOtelSpanOnClose() {
        when(tracer.spanBuilder("stage.read")).thenReturn(spanBuilder);
        when(spanBuilder.startSpan()).thenReturn(otelSpan);
        when(otelSpan.makeCurrent()).thenReturn(scope);

        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);

        try (ObservabilityHook.Span s = hook.span("stage.read")) {
            // Reference s so -Xlint doesn't flag the unused resource.
            assertThat(s).isNotNull();
        }

        // close() must end the OTel span AND close the scope.
        verify(scope).close();
        verify(otelSpan).end();
    }

    @Test
    void setAttributeAndRecordExceptionForwardToOtelSpan() {
        when(tracer.spanBuilder(any())).thenReturn(spanBuilder);
        when(spanBuilder.startSpan()).thenReturn(otelSpan);
        when(otelSpan.makeCurrent()).thenReturn(scope);

        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        ObservabilityHook.Span s = hook.span("stage.transform");

        s.setAttribute("pipeline", "demo");
        RuntimeException boom = new RuntimeException("kaboom");
        s.recordException(boom);
        s.close();

        verify(otelSpan).setAttribute("pipeline", "demo");
        verify(otelSpan).recordException(boom);
        verify(otelSpan).end();
    }

    @Test
    void spanCloseIsIdempotent() {
        when(tracer.spanBuilder(any())).thenReturn(spanBuilder);
        when(spanBuilder.startSpan()).thenReturn(otelSpan);
        when(otelSpan.makeCurrent()).thenReturn(scope);

        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        ObservabilityHook.Span s = hook.span("stage.write");

        s.close();
        s.close(); // second close must be a no-op

        verify(scope, times(1)).close();
        verify(otelSpan, times(1)).end();
    }

    // --- meter bridging ----------------------------------------------------

    @Test
    void counterDelegatesToCachedLongCounter() {
        when(meter.counterBuilder("records.read")).thenReturn(counterBuilder);
        when(counterBuilder.build()).thenReturn(counter);

        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        hook.counter("records.read", 5, Map.of("stage", "ingest"));
        hook.counter("records.read", 3, Map.of("stage", "ingest"));

        // First call creates and caches; second call must reuse — only ONE
        // builder invocation for the same metric name.
        verify(meter, times(1)).counterBuilder("records.read");
        verify(counter).add(eq(5L), any(io.opentelemetry.api.common.Attributes.class));
        verify(counter).add(eq(3L), any(io.opentelemetry.api.common.Attributes.class));
    }

    @Test
    void histogramAndGaugeUseDistinctCaches() {
        when(meter.histogramBuilder("latency_ms")).thenReturn(histogramBuilder);
        when(meter.histogramBuilder("queue_depth")).thenReturn(histogramBuilder);
        when(histogramBuilder.build()).thenReturn(histogram);

        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        hook.histogram("latency_ms", 12.5, Map.of());
        hook.gauge("queue_depth", 17.0, Map.of());

        verify(histogram).record(eq(12.5), any(io.opentelemetry.api.common.Attributes.class));
        verify(histogram).record(eq(17.0), any(io.opentelemetry.api.common.Attributes.class));
    }

    // --- log ---------------------------------------------------------------

    @Test
    void logAcceptsAllStandardLevels() {
        // Smoke test — we don't have a fixture for capturing SLF4J output
        // without pulling logback into test scope, but invoking the method
        // for each level confirms the dispatch table covers them all.
        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        Map<String, Object> fields = Map.of("run_id", "abc-123");
        hook.log("DEBUG", "d", fields);
        hook.log("INFO", "i", fields);
        hook.log("WARN", "w", fields);
        hook.log("ERROR", "e", fields);
        hook.log("info", "lowercase still routes", fields);
    }

    // --- construction ------------------------------------------------------

    @Test
    void constructorRejectsNullTracer() {
        assertThatThrownBy(() -> new CloudTraceObservabilityHook(null, meter))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullMeter() {
        assertThatThrownBy(() -> new CloudTraceObservabilityHook(tracer, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void counterRejectsNullName() {
        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);
        assertThatThrownBy(() -> hook.counter(null, 1, Map.of()))
                .isInstanceOf(NullPointerException.class);
        verify(meter, never()).counterBuilder(any());
    }

    @Test
    void counterToleratesNullTagsMap() {
        when(meter.counterBuilder(any())).thenReturn(counterBuilder);
        when(counterBuilder.build()).thenReturn(counter);
        CloudTraceObservabilityHook hook = new CloudTraceObservabilityHook(tracer, meter);

        hook.counter("free.counter", 1, null);
        verify(counter).add(anyLong(), any(io.opentelemetry.api.common.Attributes.class));
    }
}

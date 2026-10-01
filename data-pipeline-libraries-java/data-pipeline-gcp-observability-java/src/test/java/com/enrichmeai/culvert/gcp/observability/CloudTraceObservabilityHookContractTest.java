package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracttests.ObservabilityHookContractTest;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.DoubleHistogramBuilder;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.LongCounterBuilder;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link CloudTraceObservabilityHook} against the shared
 * {@link ObservabilityHookContractTest}.
 *
 * <p>The backend double is the OpenTelemetry API, mocked as in
 * {@code CloudTraceObservabilityHookTest}: each instrument records the values
 * and attributes it receives, and each span records its attributes and its
 * {@code end()}. No exporter or network is involved.
 */
class CloudTraceObservabilityHookContractTest extends ObservabilityHookContractTest {

    private final List<Metric> metrics = new ArrayList<>();
    private final List<EndedSpan> spans = new ArrayList<>();

    @Override
    protected ObservabilityHook hook() {
        Meter meter = mock(Meter.class);
        when(meter.counterBuilder(anyString())).thenAnswer(inv -> {
            String name = inv.getArgument(0);
            LongCounter counter = mock(LongCounter.class);
            doAnswer(add -> metrics.add(new Metric(name, ((Long) add.getArgument(0)).doubleValue(),
                    toMap(add.getArgument(1))))).when(counter).add(anyLong(), any(Attributes.class));
            LongCounterBuilder builder = mock(LongCounterBuilder.class);
            when(builder.build()).thenReturn(counter);
            return builder;
        });
        when(meter.histogramBuilder(anyString())).thenAnswer(inv -> {
            String name = inv.getArgument(0);
            DoubleHistogram histogram = mock(DoubleHistogram.class);
            doAnswer(rec -> metrics.add(new Metric(name, rec.getArgument(0), toMap(rec.getArgument(1)))))
                    .when(histogram).record(anyDouble(), any(Attributes.class));
            DoubleHistogramBuilder builder = mock(DoubleHistogramBuilder.class);
            when(builder.build()).thenReturn(histogram);
            return builder;
        });

        Tracer tracer = mock(Tracer.class);
        when(tracer.spanBuilder(anyString())).thenAnswer(inv -> {
            String name = inv.getArgument(0);
            Map<String, String> attributes = new LinkedHashMap<>();
            Span span = mock(Span.class);
            when(span.makeCurrent()).thenReturn(mock(Scope.class));
            doAnswer(set -> {
                attributes.put(set.getArgument(0), set.getArgument(1));
                return span;
            }).when(span).setAttribute(anyString(), anyString());
            doAnswer(end -> spans.add(new EndedSpan(name, Map.copyOf(attributes)))).when(span).end();
            SpanBuilder builder = mock(SpanBuilder.class);
            when(builder.startSpan()).thenReturn(span);
            return builder;
        });

        return new CloudTraceObservabilityHook(tracer, meter);
    }

    private static Map<String, String> toMap(Attributes attributes) {
        Map<String, String> map = new LinkedHashMap<>();
        attributes.forEach((key, value) -> map.put(key.getKey(), String.valueOf(value)));
        return map;
    }

    @Override
    protected List<Metric> metrics() {
        return metrics;
    }

    @Override
    protected List<EndedSpan> spans() {
        return spans;
    }
}

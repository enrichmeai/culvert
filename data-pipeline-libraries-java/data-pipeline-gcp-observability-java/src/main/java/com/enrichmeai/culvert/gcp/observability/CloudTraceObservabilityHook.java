package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.metrics.DoubleHistogram;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

/**
 * {@link ObservabilityHook} implementation backed by OpenTelemetry whose
 * tracer / meter providers export to Google Cloud Trace and Google Cloud
 * Monitoring.
 *
 * <p>Wiring is decoupled from this class: callers construct an
 * {@link OpenTelemetry} instance whose {@code SdkTracerProvider} has a
 * {@code TraceExporter} from the
 * {@code com.google.cloud.opentelemetry:exporter-trace} artifact registered
 * (typically via a {@code BatchSpanProcessor}). This class wraps the
 * resulting {@link Tracer} and {@link Meter} and bridges them to the Culvert
 * {@link ObservabilityHook} surface.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #CloudTraceObservabilityHook()} — no-arg, for {@link java.util.ServiceLoader}
 *       discovery (T12.6). Wraps {@link io.opentelemetry.api.GlobalOpenTelemetry#get()} with a
 *       fixed instrumentation scope ({@value #DEFAULT_INSTRUMENTATION_SCOPE}). Consistent with
 *       the class design: wiring the OTel exporter to Cloud Trace is the caller's responsibility;
 *       if the global OTel SDK is configured with a GCP trace exporter, this hook transparently
 *       emits to Cloud Trace. If only the no-op global is installed, spans are discarded — this
 *       is the expected fallback when the module is on the classpath but no OTel SDK is wired.
 *       This constructor never throws — {@link io.opentelemetry.api.GlobalOpenTelemetry#get()}
 *       always returns a non-null instance.</li>
 *   <li>{@link #CloudTraceObservabilityHook(OpenTelemetry, String)} — primary;
 *       caller supplies an OTel instance + an instrumentation scope name
 *       (typically the pipeline name).</li>
 *   <li>{@link #CloudTraceObservabilityHook(Tracer, Meter)} — for tests; wraps
 *       an already-resolved {@link Tracer} and {@link Meter} so callers can
 *       inject mocks directly.</li>
 * </ul>
 *
 * <h2>Bridging the contract</h2>
 * <ul>
 *   <li>{@code counter}/{@code gauge}/{@code histogram} → OTel {@link Meter}
 *       instruments, lazily created and cached by name.</li>
 *   <li>{@code log} → SLF4J at the requested level. The {@code fields} map is
 *       rendered as {@code key=value} pairs appended to the message (SLF4J
 *       has no structured-field API in core, so this keeps the log line
 *       self-contained without forcing a logback / MDC dependency).</li>
 *   <li>{@code span} → OTel {@link Tracer}; the returned {@link Span} wraps
 *       the OTel {@code Span}+{@code Scope} pair and closes both on
 *       {@link Span#close()}.</li>
 * </ul>
 *
 * <p>This class does <strong>not</strong> implement {@link AutoCloseable}:
 * the wrapped {@link OpenTelemetry} interface is not closeable; lifecycle
 * (flushing the BatchSpanProcessor on shutdown) belongs to whoever built
 * the SDK. Mirrors the {@code BigQueryWarehouse} "AutoCloseable only when
 * the wrapped client supports it" rule.
 *
 * <p>Sprint-2 deliverable for issue #24; no-arg ctor added Sprint-12 T12.6 (issue #91).
 */
public final class CloudTraceObservabilityHook implements ObservabilityHook {

    private static final Logger LOG = LoggerFactory.getLogger(CloudTraceObservabilityHook.class);

    /**
     * Default instrumentation scope used by the no-arg constructor.
     *
     * <p>An instrumentation scope identifies the library or component that produces spans.
     * When wired via ServiceLoader, the scope is fixed to this constant; callers that need
     * a pipeline-specific scope should use the {@link #CloudTraceObservabilityHook(OpenTelemetry, String)}
     * constructor directly.
     */
    static final String DEFAULT_INSTRUMENTATION_SCOPE = "com.enrichmeai.culvert";

    private final Tracer tracer;
    private final Meter meter;

    // Instrument caches — OTel meters require us to register instruments
    // by name; reusing instances avoids re-registration cost and keeps
    // metric IDs stable across calls.
    private final Map<String, LongCounter> counters = new ConcurrentHashMap<>();
    private final Map<String, DoubleHistogram> histograms = new ConcurrentHashMap<>();
    private final Map<String, DoubleHistogram> gauges = new ConcurrentHashMap<>();

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery (T12.6).
     *
     * <p>Wraps {@link io.opentelemetry.api.GlobalOpenTelemetry#get()} with the fixed
     * instrumentation scope {@value #DEFAULT_INSTRUMENTATION_SCOPE}. Consistent with this
     * class's stated design: wiring the OTel SDK to export to Cloud Trace is the caller's
     * responsibility (via a {@code TraceExporter} + {@code BatchSpanProcessor} on the
     * {@code SdkTracerProvider}). If the global OTel is configured with such an exporter,
     * spans are emitted to Cloud Trace. If the no-op global is installed (e.g. when no
     * OTel SDK is on the classpath), spans are discarded — this is the expected graceful
     * fallback.
     *
     * <p>This constructor <strong>never throws</strong>:
     * {@link io.opentelemetry.api.GlobalOpenTelemetry#get()} always returns a non-null
     * instance, and {@link OpenTelemetry#getTracer}/{@link OpenTelemetry#getMeter} are
     * similarly non-throwing. This makes the class unconditionally instantiable by
     * ServiceLoader — the SPI registration is now real (T12.6).
     */
    public CloudTraceObservabilityHook() {
        this(io.opentelemetry.api.GlobalOpenTelemetry.get(), DEFAULT_INSTRUMENTATION_SCOPE);
    }

    /**
     * Primary constructor.
     *
     * @param otel               Configured OpenTelemetry instance whose tracer
     *                           provider exports to Cloud Trace. Required.
     * @param instrumentationScope Name passed to {@code getTracer} /
     *                           {@code getMeter} — typically the pipeline
     *                           name. Required.
     * @throws NullPointerException if either argument is null.
     */
    public CloudTraceObservabilityHook(OpenTelemetry otel, String instrumentationScope) {
        Objects.requireNonNull(otel, "otel must not be null");
        Objects.requireNonNull(instrumentationScope, "instrumentationScope must not be null");
        this.tracer = otel.getTracer(instrumentationScope);
        this.meter = otel.getMeter(instrumentationScope);
    }

    /**
     * Test-friendly constructor that takes pre-resolved {@link Tracer} and
     * {@link Meter}. Both are required.
     *
     * @throws NullPointerException if either argument is null.
     */
    public CloudTraceObservabilityHook(Tracer tracer, Meter meter) {
        this.tracer = Objects.requireNonNull(tracer, "tracer must not be null");
        this.meter = Objects.requireNonNull(meter, "meter must not be null");
    }

    @Override
    public void counter(String name, long value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name");
        LongCounter c = counters.computeIfAbsent(name, n -> meter.counterBuilder(n).build());
        c.add(value, toAttributes(tags));
    }

    @Override
    public void gauge(String name, double value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name");
        // OpenTelemetry's "synchronous gauge" landed in 1.40+. For 1.38 we
        // surface gauges as a single-shot histogram observation — this keeps
        // the value visible in Cloud Monitoring without requiring async
        // callbacks. When the SDK is bumped to 1.40+ this should switch to
        // meter.gaugeBuilder(name).build().
        DoubleHistogram g = gauges.computeIfAbsent(
                name, n -> meter.histogramBuilder(n).build());
        g.record(value, toAttributes(tags));
    }

    @Override
    public void histogram(String name, double value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name");
        DoubleHistogram h = histograms.computeIfAbsent(
                name, n -> meter.histogramBuilder(n).build());
        h.record(value, toAttributes(tags));
    }

    @Override
    public void log(String level, String message, Map<String, Object> fields) {
        Objects.requireNonNull(level, "level");
        Objects.requireNonNull(message, "message");
        String rendered = renderFields(message, fields);
        String upper = level.toUpperCase(java.util.Locale.ROOT);
        switch (upper) {
            case "DEBUG" -> LOG.debug(rendered);
            case "INFO" -> LOG.info(rendered);
            case "WARN" -> LOG.warn(rendered);
            case "ERROR" -> LOG.error(rendered);
            default -> LOG.info(rendered);
        }
    }

    @Override
    public Span span(String name) {
        Objects.requireNonNull(name, "name");
        io.opentelemetry.api.trace.Span otelSpan = tracer.spanBuilder(name).startSpan();
        Scope scope = otelSpan.makeCurrent();
        return new OtelSpanAdapter(otelSpan, scope);
    }

    // --- helpers ----------------------------------------------------------

    private static io.opentelemetry.api.common.Attributes toAttributes(Map<String, String> tags) {
        if (tags == null || tags.isEmpty()) {
            return io.opentelemetry.api.common.Attributes.empty();
        }
        var builder = io.opentelemetry.api.common.Attributes.builder();
        for (Map.Entry<String, String> e : tags.entrySet()) {
            if (e.getKey() != null && e.getValue() != null) {
                builder.put(AttributeKey.stringKey(e.getKey()), e.getValue());
            }
        }
        return builder.build();
    }

    private static String renderFields(String message, Map<String, Object> fields) {
        if (fields == null || fields.isEmpty()) {
            return message;
        }
        StringBuilder sb = new StringBuilder(message);
        sb.append(' ');
        boolean first = true;
        for (Map.Entry<String, Object> e : fields.entrySet()) {
            if (!first) {
                sb.append(' ');
            }
            sb.append(e.getKey()).append('=').append(e.getValue());
            first = false;
        }
        return sb.toString();
    }

    /**
     * Adapter from Culvert {@link Span} to OpenTelemetry's
     * {@code Span}+{@code Scope} pair. Idempotent on {@link #close()} — a
     * double-close is a no-op rather than throwing, matching the
     * try-with-resources expectations of the contract.
     */
    static final class OtelSpanAdapter implements Span {
        private final io.opentelemetry.api.trace.Span span;
        private final Scope scope;
        private boolean closed;

        OtelSpanAdapter(io.opentelemetry.api.trace.Span span, Scope scope) {
            this.span = span;
            this.scope = scope;
        }

        @Override
        public void setAttribute(String key, String value) {
            Objects.requireNonNull(key, "key");
            Objects.requireNonNull(value, "value");
            span.setAttribute(key, value);
        }

        @Override
        public void recordException(Throwable t) {
            Objects.requireNonNull(t, "t");
            span.recordException(t);
        }

        @Override
        public void close() {
            if (closed) {
                return;
            }
            closed = true;
            try {
                scope.close();
            } finally {
                span.end();
            }
        }
    }
}

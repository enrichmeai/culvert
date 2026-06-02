package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.ObservabilityHook;

import java.io.Serializable;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Serializable recording {@link ObservabilityHook} for the S12 observability E2E test.
 *
 * <p>Registered via {@code META-INF/services/com.enrichmeai.culvert.contracts.ObservabilityHook}
 * so that {@code AutoConfig.discover()} picks it up during driver-side construction and
 * worker-side registry rebuild after Beam serialization. Proves the tracing seam
 * ({@link ObservabilityHook#span(String)}) fires automatically for every stage — no
 * per-stage boilerplate (epic #47).
 *
 * <p>Span start/end events are captured in {@code static} {@link CopyOnWriteArrayList}
 * fields, visible on the DirectRunner's in-process worker. Tests clear via {@link #reset()}
 * in {@code @BeforeEach}.
 *
 * <p>T12.5 / issue #80 — Sprint-12 observability slice.
 */
public final class RecordingObservabilityHook implements ObservabilityHook, Serializable {

    private static final long serialVersionUID = 1L;

    /** Names of spans opened (one per stage execution). Format: {@code culvert.stage/<name>}. */
    public static final CopyOnWriteArrayList<String> SPANS_OPENED = new CopyOnWriteArrayList<>();

    /** Names of spans closed (one per stage execution, even on error — closed in finally). */
    public static final CopyOnWriteArrayList<String> SPANS_CLOSED = new CopyOnWriteArrayList<>();

    /**
     * No-arg constructor required by {@link java.util.ServiceLoader}.
     * Also required for Beam DoFn serialization round-trip.
     */
    public RecordingObservabilityHook() {
        // ServiceLoader / Beam serialization entry point.
    }

    @Override
    public void counter(String name, long value, Map<String, String> tags) {
        // T12.4: error/latency counters moved to StageMetricsHook; not recorded here.
    }

    @Override
    public void gauge(String name, double value, Map<String, String> tags) {
        // Not exercised in the reference E2E test.
    }

    @Override
    public void histogram(String name, double value, Map<String, String> tags) {
        // T12.4: latency moved to StageMetricsHook; not recorded here.
    }

    @Override
    public void log(String level, String message, Map<String, Object> fields) {
        // Not captured; MDC population is asserted via SLF4J MDC in unit tests.
    }

    @Override
    public Span span(String name) {
        SPANS_OPENED.add(name);
        return new RecordingSpan(name);
    }

    /** Reset all static recording surfaces — call from {@code @BeforeEach}. */
    public static void reset() {
        SPANS_OPENED.clear();
        SPANS_CLOSED.clear();
    }

    /**
     * A serializable span that records its close into {@link #SPANS_CLOSED}.
     */
    static final class RecordingSpan implements ObservabilityHook.Span, Serializable {

        private static final long serialVersionUID = 1L;

        private final String name;
        private boolean closed;

        RecordingSpan(String name) {
            this.name = name;
        }

        @Override
        public void setAttribute(String key, String value) {
            // not captured in this E2E test
        }

        @Override
        public void recordException(Throwable t) {
            // not captured in this E2E test
        }

        @Override
        public void close() {
            if (!closed) {
                closed = true;
                SPANS_CLOSED.add(name);
            }
        }
    }
}

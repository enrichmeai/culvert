package com.enrichmeai.culvert.contracts;

import java.util.Map;

/**
 * The framework's single observability seam.
 *
 * <p>Metrics, structured logs, and tracing all flow through this interface.
 * Implementations may compose multiple backends internally (a typical Java
 * implementation delegates metrics to Micrometer or OTEL, logs to SLF4J,
 * tracing to OpenTelemetry). User code has one dependency to inject, not
 * three.
 *
 * <p>{@code tags} follow OpenTelemetry attribute conventions (string keys,
 * string values). High-cardinality tag values (e.g. {@code runId}) should be
 * added to spans/logs but kept off metric labels.
 *
 * <p>Java mirror of the Python {@code ObservabilityHook} Protocol.
 */
public interface ObservabilityHook {

    /** Increment a monotonic counter named {@code name} by {@code value}. */
    void counter(String name, long value, Map<String, String> tags);

    /** Set the current value of gauge {@code name} to {@code value}. */
    void gauge(String name, double value, Map<String, String> tags);

    /** Record an observation of {@code value} into histogram {@code name}. */
    void histogram(String name, double value, Map<String, String> tags);

    /**
     * Emit a structured log line.
     *
     * @param level  One of {@code DEBUG}/{@code INFO}/{@code WARN}/{@code ERROR}
     *               (case-insensitive).
     * @param message The log message.
     * @param fields Structured attributes on the log record.
     */
    void log(String level, String message, Map<String, Object> fields);

    /**
     * Open a tracing span named {@code name}.
     *
     * <p>The returned {@link Span} must be closed (use try-with-resources).
     * Exceptions thrown inside the {@code try} block are recorded on the span.
     */
    Span span(String name);

    /**
     * A tracing span handle. Implements {@link AutoCloseable} for
     * try-with-resources usage.
     */
    interface Span extends AutoCloseable {
        /** Annotate the span with a key/value attribute. */
        void setAttribute(String key, String value);

        /** Record an exception on the span. */
        void recordException(Throwable t);

        @Override
        void close();
    }
}

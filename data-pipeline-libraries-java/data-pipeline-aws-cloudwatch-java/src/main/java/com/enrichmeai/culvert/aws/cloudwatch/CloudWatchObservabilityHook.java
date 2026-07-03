package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.Dimension;
import software.amazon.awssdk.services.cloudwatch.model.MetricDatum;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataRequest;
import software.amazon.awssdk.services.cloudwatch.model.StandardUnit;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;

/**
 * {@link ObservabilityHook} implementation that emits Culvert counters,
 * gauges, and histograms to Amazon CloudWatch via the CloudWatch {@code
 * PutMetricData} API ({@link CloudWatchClient}), and delegates structured
 * logs to SLF4J.
 *
 * <h2>Module placement decision</h2>
 * <p>This class lives in {@code data-pipeline-aws-cloudwatch-java}, the AWS
 * counterpart of {@code data-pipeline-gcp-observability-java}'s {@code
 * CloudTraceObservabilityHook}. The cloud-neutral {@link ObservabilityHook}
 * type lives in {@code data-pipeline-core-java} with zero AWS imports.
 *
 * <h2>Bridging the contract</h2>
 * <ul>
 *   <li>{@code counter} -&gt; a {@link MetricDatum} with
 *       {@link StandardUnit#COUNT}, published as-is (CloudWatch has no
 *       client-side accumulation the way an OTel {@code LongCounter} does;
 *       each call is one data point, and CloudWatch aggregates same-name /
 *       same-dimension points server-side when graphed with the Sum
 *       statistic).</li>
 *   <li>{@code gauge} -&gt; a {@link MetricDatum} with
 *       {@link StandardUnit#NONE}, the current instantaneous value.</li>
 *   <li>{@code histogram} -&gt; a {@link MetricDatum} with
 *       {@link StandardUnit#NONE}, one data point per observation.
 *       CloudWatch has no native histogram/distribution API accessible via
 *       plain {@code PutMetricData} (unlike OTel's {@code DoubleHistogram});
 *       publishing the raw observation and letting CloudWatch's
 *       {@code p50}/{@code p99} percentile statistics aggregate across
 *       data points is the standard CloudWatch-native approximation.</li>
 *   <li>{@code log} -&gt; SLF4J at the requested level. The {@code fields}
 *       map is rendered as {@code key=value} pairs appended to the message —
 *       same rendering as {@code CloudTraceObservabilityHook}, so log
 *       shape is consistent across cloud adapters.</li>
 *   <li>{@code span} -&gt; see below.</li>
 * </ul>
 *
 * <h2>Span handling — design choice</h2>
 * <p>CloudWatch (via plain {@code PutMetricData}) has no native distributed
 * tracing primitive the way Cloud Trace / OpenTelemetry does; AWS's tracing
 * story lives in X-Ray, a separate service and SDK this module deliberately
 * does not take a dependency on (staying narrowly scoped to CloudWatch
 * metrics, per this ticket). Instead, {@link #span(String)} returns a
 * <strong>lightweight timer</strong>: it records the start {@link Instant}
 * on open, and on {@link Span#close()} emits a single gauge-style {@link
 * MetricDatum} named {@code <name>.duration_ms} (unit {@link
 * StandardUnit#MILLISECONDS}) carrying the elapsed wall-clock time. This
 * gives operators a duration signal per named span in CloudWatch without
 * pulling in X-Ray. {@code setAttribute} calls are folded into the emitted
 * datum's dimensions (attributes set before {@code close()} become
 * dimensions on the duration metric); {@code recordException} increments a
 * companion {@code <name>.exception_count} counter metric on close. This is
 * a deliberately reduced substitute for a real span/trace — callers that
 * need actual distributed tracing on AWS should compose this hook with an
 * X-Ray-backed tracer rather than relying on {@link #span(String)} alone.
 *
 * <h2>Monitoring failures</h2>
 * Any exception thrown by {@link CloudWatchClient#putMetricData} is caught,
 * logged at WARN level, and swallowed — mirrors {@link
 * CloudWatchStageMetricsHook}'s resilience contract. Metric-emission
 * failures never propagate to caller code.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #CloudWatchObservabilityHook()} — no-arg, for {@link
 *       java.util.ServiceLoader} discovery. Builds a default {@link
 *       CloudWatchClient} via {@code CloudWatchClient.create()} and resolves
 *       the namespace from the same precedence chain as {@link
 *       CloudWatchStageMetricsHook}: system property {@value
 *       CloudWatchStageMetricsHook#SYSPROP_NAMESPACE}, then environment
 *       variable {@value CloudWatchStageMetricsHook#ENVVAR_NAMESPACE}, then
 *       {@value CloudWatchStageMetricsHook#DEFAULT_NAMESPACE}.</li>
 *   <li>{@link #CloudWatchObservabilityHook(CloudWatchClient, String)} —
 *       primary for tests and custom-credential wiring. Ownership of the
 *       client transfers to this hook ({@link #close()} will close it).</li>
 * </ul>
 *
 * <p>Implements {@link AutoCloseable}: closing this hook closes the
 * underlying {@link CloudWatchClient}.
 *
 * <p>Sprint-21 deliverable for issue #150 (T21.6, epic #144).
 */
public final class CloudWatchObservabilityHook implements ObservabilityHook, AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(CloudWatchObservabilityHook.class);

    private final CloudWatchClient client;
    private final String namespace;
    private final AtomicLong monitoringFailures = new AtomicLong();

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery.
     *
     * <p>Builds a default {@link CloudWatchClient} from the AWS SDK's
     * default region and credential provider chains, and resolves the
     * namespace using {@link CloudWatchStageMetricsHook#resolveNamespace()}.
     */
    public CloudWatchObservabilityHook() {
        this(CloudWatchClient.create(), CloudWatchStageMetricsHook.resolveNamespace());
    }

    /**
     * Explicit constructor for tests and custom-credential wiring.
     *
     * @param client    Pre-built CloudWatch client. Required. Ownership
     *                  transfers to this hook — {@link #close()} will close it.
     * @param namespace CloudWatch namespace to publish under. Required.
     * @throws NullPointerException if either argument is null.
     */
    public CloudWatchObservabilityHook(CloudWatchClient client, String namespace) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.namespace = Objects.requireNonNull(namespace, "namespace must not be null");
    }

    @Override
    public void counter(String name, long value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name must not be null");
        putDatum(name, (double) value, StandardUnit.COUNT, tags);
    }

    @Override
    public void gauge(String name, double value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name must not be null");
        putDatum(name, value, StandardUnit.NONE, tags);
    }

    @Override
    public void histogram(String name, double value, Map<String, String> tags) {
        Objects.requireNonNull(name, "name must not be null");
        putDatum(name, value, StandardUnit.NONE, tags);
    }

    @Override
    public void log(String level, String message, Map<String, Object> fields) {
        Objects.requireNonNull(level, "level must not be null");
        Objects.requireNonNull(message, "message must not be null");
        String rendered = renderFields(message, fields);
        switch (level.toUpperCase(Locale.ROOT)) {
            case "DEBUG" -> LOG.debug(rendered);
            case "INFO" -> LOG.info(rendered);
            case "WARN" -> LOG.warn(rendered);
            case "ERROR" -> LOG.error(rendered);
            default -> LOG.info(rendered);
        }
    }

    @Override
    public Span span(String name) {
        Objects.requireNonNull(name, "name must not be null");
        return new CloudWatchTimerSpan(name);
    }

    /**
     * Returns the cumulative count of monitoring write failures since this
     * hook was constructed. Useful in tests and operational alerting.
     */
    public long monitoringFailureCount() {
        return monitoringFailures.get();
    }

    /** CloudWatch namespace this hook publishes to. */
    public String namespace() {
        return namespace;
    }

    @Override
    public void close() {
        client.close();
    }

    // --- helpers -------------------------------------------------------------

    private void putDatum(String name, double value, StandardUnit unit, Map<String, String> tags) {
        MetricDatum.Builder builder = MetricDatum.builder()
                .metricName(name)
                .timestamp(Instant.now())
                .unit(unit)
                .value(value);
        List<Dimension> dimensions = toDimensions(tags);
        if (!dimensions.isEmpty()) {
            builder.dimensions(dimensions);
        }
        publish(builder.build());
    }

    private void publish(MetricDatum datum) {
        PutMetricDataRequest request = PutMetricDataRequest.builder()
                .namespace(namespace)
                .metricData(List.of(datum))
                .build();
        try {
            client.putMetricData(request);
        } catch (Exception ex) {
            monitoringFailures.incrementAndGet();
            LOG.warn("CloudWatchObservabilityHook: failed to write metric {}; "
                    + "monitoring error swallowed", datum.metricName(), ex);
        }
    }

    private static List<Dimension> toDimensions(Map<String, String> tags) {
        if (tags == null || tags.isEmpty()) {
            return List.of();
        }
        return tags.entrySet().stream()
                .filter(e -> e.getKey() != null && e.getValue() != null)
                .map(e -> Dimension.builder().name(e.getKey()).value(e.getValue()).build())
                .toList();
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
     * Lightweight timer-based {@link Span} substitute. See the class
     * Javadoc "Span handling — design choice" section for the rationale.
     *
     * <p>Idempotent on {@link #close()} — a double-close is a no-op rather
     * than throwing, matching the try-with-resources expectations of the
     * contract (mirrors {@code CloudTraceObservabilityHook.OtelSpanAdapter}).
     */
    final class CloudWatchTimerSpan implements Span {
        private final String name;
        private final Instant start;
        private final java.util.Map<String, String> attributes = new java.util.LinkedHashMap<>();
        private Throwable recordedException;
        private boolean closed;

        CloudWatchTimerSpan(String name) {
            this.name = name;
            this.start = Instant.now();
        }

        @Override
        public void setAttribute(String key, String value) {
            Objects.requireNonNull(key, "key must not be null");
            Objects.requireNonNull(value, "value must not be null");
            attributes.put(key, value);
        }

        @Override
        public void recordException(Throwable t) {
            Objects.requireNonNull(t, "t must not be null");
            recordedException = t;
        }

        @Override
        public void close() {
            if (closed) {
                return;
            }
            closed = true;

            long elapsedMs = java.time.Duration.between(start, Instant.now()).toMillis();
            putDatum(name + ".duration_ms", (double) elapsedMs, StandardUnit.MILLISECONDS, attributes);

            if (recordedException != null) {
                putDatum(name + ".exception_count", 1.0, StandardUnit.COUNT, attributes);
            }
        }
    }
}

package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.Dimension;
import software.amazon.awssdk.services.cloudwatch.model.MetricDatum;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataRequest;
import software.amazon.awssdk.services.cloudwatch.model.StandardUnit;

import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;

/**
 * {@link StageMetricsHook} implementation that emits Culvert pipeline metrics
 * to Amazon CloudWatch via the CloudWatch {@code PutMetricData} API
 * ({@link CloudWatchClient}).
 *
 * <h2>Module placement decision</h2>
 * <p>This class lives in {@code data-pipeline-aws-cloudwatch-java}, the AWS
 * counterpart of {@code data-pipeline-gcp-observability-java}'s {@code
 * CloudMonitoringMetricsHook}. Metric names, the three-metric set, and the
 * label schema are mirrored exactly from that reference implementation so
 * the two clouds report the same Culvert-level signal under different
 * transports. The cloud-neutral {@link StageMetricsHook} / {@link
 * StageMetrics} types live in {@code data-pipeline-core-java} with zero AWS
 * imports.
 *
 * <h2>Metric schema</h2>
 * <table border="1">
 *   <tr><th>Metric name</th><th>Unit</th></tr>
 *   <tr><td>{@code culvert/rows_processed}</td><td>{@code Count}</td></tr>
 *   <tr><td>{@code culvert/stage_latency_ms}</td><td>{@code Milliseconds}</td></tr>
 *   <tr><td>{@code culvert/error_count}</td><td>{@code Count}</td></tr>
 * </table>
 *
 * <p>Unlike Cloud Monitoring, CloudWatch has no first-class CUMULATIVE vs.
 * GAUGE metric-kind distinction on the wire — every {@link MetricDatum} is
 * just a timestamped value (or statistic set) under a metric name plus
 * dimensions. CloudWatch itself aggregates same-name/same-dimension data
 * points published within a window; whether a metric reads as a "rate" or a
 * "level" downstream is a property of how it's graphed (e.g. Sum vs. Average
 * statistic), not of the datum itself. All three data points here are
 * published as plain instantaneous values with the current timestamp.
 *
 * <h2>Namespace</h2>
 * <p>All three data points are published under a single configurable
 * CloudWatch namespace, defaulting to {@value #DEFAULT_NAMESPACE}.
 *
 * <h2>Labels -&gt; Dimensions</h2>
 * All three data points carry the dimensions {@code pipeline_id}, {@code
 * run_id}, {@code stage_name} as specified by the {@link StageMetrics}
 * snapshot — the same label schema as {@code CloudMonitoringMetricsHook}.
 *
 * <h2>Monitoring failures</h2>
 * Any exception thrown by {@link CloudWatchClient#putMetricData} is caught,
 * logged at WARN level, and swallowed. The pipeline is never interrupted by
 * a monitoring backend error. The failure count is accessible via {@link
 * #monitoringFailureCount()} for tests and operational alerting. Mirrors
 * {@code CloudMonitoringMetricsHook}'s resilience contract exactly.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #CloudWatchStageMetricsHook()} — no-arg, for {@link
 *       java.util.ServiceLoader} discovery. Builds a default {@link
 *       CloudWatchClient} via {@code CloudWatchClient.create()} (default AWS
 *       region/credential provider chains) and resolves the namespace from
 *       the following precedence chain:
 *       <ol>
 *         <li>System property {@value #SYSPROP_NAMESPACE}</li>
 *         <li>Environment variable {@value #ENVVAR_NAMESPACE}</li>
 *         <li>{@value #DEFAULT_NAMESPACE}</li>
 *       </ol>
 *   </li>
 *   <li>{@link #CloudWatchStageMetricsHook(CloudWatchClient, String)} —
 *       primary for tests and custom-credential wiring. Inject a pre-built
 *       client and explicit namespace. Ownership of the client transfers to
 *       this hook ({@link #close()} will close it).
 *   </li>
 * </ul>
 *
 * <p>Implements {@link AutoCloseable}: closing this hook closes the
 * underlying {@link CloudWatchClient}. Mirrors the {@code
 * CloudMonitoringMetricsHook} lifecycle contract.
 *
 * <p>Sprint-21 deliverable for issue #150 (T21.6, epic #144).
 */
public final class CloudWatchStageMetricsHook implements StageMetricsHook, AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(CloudWatchStageMetricsHook.class);

    /** Metric name for rows_processed. */
    static final String METRIC_ROWS_PROCESSED = "culvert/rows_processed";

    /** Metric name for stage_latency_ms. */
    static final String METRIC_STAGE_LATENCY_MS = "culvert/stage_latency_ms";

    /** Metric name for error_count. */
    static final String METRIC_ERROR_COUNT = "culvert/error_count";

    /** Default CloudWatch namespace used when none is configured. */
    static final String DEFAULT_NAMESPACE = "Culvert";

    /** System property key for the namespace override. */
    static final String SYSPROP_NAMESPACE = "culvert.aws.cloudwatch.namespace";

    /** Environment variable key for the namespace override. */
    static final String ENVVAR_NAMESPACE = "CULVERT_AWS_CLOUDWATCH_NAMESPACE";

    private final CloudWatchClient client;
    private final String namespace;
    private final AtomicLong monitoringFailures = new AtomicLong();

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery.
     *
     * <p>Builds a default {@link CloudWatchClient} from the AWS SDK's
     * default region and credential provider chains, and resolves the
     * namespace from the precedence chain documented on the class.
     */
    public CloudWatchStageMetricsHook() {
        this(CloudWatchClient.create(), resolveNamespace());
    }

    /**
     * Explicit constructor for tests and custom-credential wiring.
     *
     * @param client    Pre-built CloudWatch client. Required. Ownership
     *                  transfers to this hook — {@link #close()} will close it.
     * @param namespace CloudWatch namespace to publish under. Required.
     * @throws NullPointerException if either argument is null.
     */
    public CloudWatchStageMetricsHook(CloudWatchClient client, String namespace) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.namespace = Objects.requireNonNull(namespace, "namespace must not be null");
    }

    /**
     * Resolves the CloudWatch namespace using the precedence chain
     * documented on the class: system property, then environment variable,
     * then {@value #DEFAULT_NAMESPACE}.
     *
     * <p>Package-private for testing.
     *
     * @return non-blank namespace string
     */
    static String resolveNamespace() {
        String fromProp = System.getProperty(SYSPROP_NAMESPACE);
        if (fromProp != null && !fromProp.isBlank()) {
            return fromProp;
        }
        String fromEnv = System.getenv(ENVVAR_NAMESPACE);
        if (fromEnv != null && !fromEnv.isBlank()) {
            return fromEnv;
        }
        return DEFAULT_NAMESPACE;
    }

    /**
     * Emit all three Culvert metrics for a completed stage to CloudWatch.
     *
     * <p>A single {@code PutMetricData} RPC carries all three {@link
     * MetricDatum} objects. If the RPC fails the exception is logged and
     * swallowed — monitoring failures never interrupt the pipeline.
     *
     * @param metrics Stage metrics snapshot. Must not be null.
     */
    @Override
    public void recordStageMetrics(StageMetrics metrics) {
        Objects.requireNonNull(metrics, "metrics must not be null");

        Instant now = Instant.now();
        List<Dimension> dimensions = buildDimensions(metrics);

        MetricDatum rowsDatum = MetricDatum.builder()
                .metricName(METRIC_ROWS_PROCESSED)
                .dimensions(dimensions)
                .timestamp(now)
                .unit(StandardUnit.COUNT)
                .value((double) metrics.rowsProcessed())
                .build();

        MetricDatum latencyDatum = MetricDatum.builder()
                .metricName(METRIC_STAGE_LATENCY_MS)
                .dimensions(dimensions)
                .timestamp(now)
                .unit(StandardUnit.MILLISECONDS)
                .value(metrics.stageLatencyMs())
                .build();

        MetricDatum errorDatum = MetricDatum.builder()
                .metricName(METRIC_ERROR_COUNT)
                .dimensions(dimensions)
                .timestamp(now)
                .unit(StandardUnit.COUNT)
                .value((double) metrics.errorCount())
                .build();

        PutMetricDataRequest request = PutMetricDataRequest.builder()
                .namespace(namespace)
                .metricData(List.of(rowsDatum, latencyDatum, errorDatum))
                .build();

        try {
            client.putMetricData(request);
        } catch (Exception ex) {
            monitoringFailures.incrementAndGet();
            LOG.warn("CloudWatchStageMetricsHook: failed to write metrics for "
                    + "pipeline={} run={} stage={}; monitoring error swallowed",
                    metrics.pipelineId(), metrics.runId(), metrics.stageName(), ex);
        }
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

    private static List<Dimension> buildDimensions(StageMetrics metrics) {
        return List.of(
                Dimension.builder().name("pipeline_id").value(metrics.pipelineId()).build(),
                Dimension.builder().name("run_id").value(metrics.runId()).build(),
                Dimension.builder().name("stage_name").value(metrics.stageName()).build());
    }
}

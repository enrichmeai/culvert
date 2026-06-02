package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.google.api.MetricDescriptor;
import com.google.api.MonitoredResource;
import com.google.cloud.monitoring.v3.MetricServiceClient;
import com.google.monitoring.v3.CreateTimeSeriesRequest;
import com.google.monitoring.v3.Point;
import com.google.monitoring.v3.ProjectName;
import com.google.monitoring.v3.TimeInterval;
import com.google.monitoring.v3.TimeSeries;
import com.google.monitoring.v3.TypedValue;
import com.google.protobuf.util.Timestamps;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;

/**
 * {@link StageMetricsHook} implementation that emits Culvert pipeline metrics
 * to Google Cloud Monitoring via the Cloud Monitoring v3 API
 * ({@link MetricServiceClient}).
 *
 * <h2>Module placement decision (per issue #65)</h2>
 * <p>This class lives in {@code data-pipeline-gcp-observability-java} —
 * the same module that already contains {@link CloudTraceObservabilityHook}
 * and {@link DataCatalogLineageEmitter}. A new module is not warranted:
 * the module is already a multi-contract GCP observability adapter, and
 * {@code google-cloud-monitoring} is a peer GCP library of similar size.
 * The cloud-neutral {@link StageMetricsHook} / {@link StageMetrics} types
 * live in {@code data-pipeline-core-java} with zero GCP imports.
 *
 * <h2>Metric schema</h2>
 * <table border="1">
 *   <tr><th>Metric type</th><th>Kind</th><th>Value type</th></tr>
 *   <tr>
 *     <td>{@code custom.googleapis.com/culvert/rows_processed}</td>
 *     <td>CUMULATIVE</td><td>INT64</td>
 *   </tr>
 *   <tr>
 *     <td>{@code custom.googleapis.com/culvert/stage_latency_ms}</td>
 *     <td>GAUGE</td><td>DOUBLE</td>
 *   </tr>
 *   <tr>
 *     <td>{@code custom.googleapis.com/culvert/error_count}</td>
 *     <td>CUMULATIVE</td><td>INT64</td>
 *   </tr>
 * </table>
 *
 * <h2>Labels</h2>
 * All three time series carry the labels {@code pipeline_id}, {@code run_id},
 * {@code stage_name} as specified by the {@link StageMetrics} snapshot.
 *
 * <h2>Monitoring failures</h2>
 * Any exception thrown by {@link MetricServiceClient#createTimeSeries} is
 * caught, logged at WARN level, and swallowed. The pipeline is never
 * interrupted by a monitoring backend error. The failure count is accessible
 * via {@link #monitoringFailureCount()} for tests and operational alerting.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #CloudMonitoringMetricsHook()} — no-arg, for {@link java.util.ServiceLoader}
 *       discovery. Resolves the project-id from the following precedence chain:
 *       <ol>
 *         <li>System property {@code culvert.gcp.project}</li>
 *         <li>Environment variable {@code CULVERT_GCP_PROJECT}</li>
 *         <li>ADC default via {@code com.google.cloud.ServiceOptions.getDefaultProjectId()}</li>
 *       </ol>
 *       Throws {@link IllegalStateException} if none of the three yields a non-blank value.
 *       Builds the {@link MetricServiceClient} via its {@code create()} factory (ADC). This
 *       constructor is the {@link java.util.ServiceLoader} entry point — it makes the
 *       {@code META-INF/services} SPI registration real (T12.6).
 *   </li>
 *   <li>{@link #CloudMonitoringMetricsHook(MetricServiceClient, String)} — primary for tests
 *       and custom-credential wiring. Inject a pre-built client and explicit project-id.
 *       Ownership of the client transfers to this hook ({@link #close()} will close it).
 *   </li>
 * </ul>
 *
 * <p>Implements {@link AutoCloseable}: closing this hook closes the
 * underlying {@link MetricServiceClient} (which implements
 * {@link com.google.api.gax.core.BackgroundResource}). Mirrors the
 * {@link DataCatalogLineageEmitter} lifecycle contract.
 *
 * <p>Sprint-12 deliverable for issues #65 (T12.1) and #91 (T12.6 — no-arg ctor).
 */
public final class CloudMonitoringMetricsHook implements StageMetricsHook, AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(CloudMonitoringMetricsHook.class);

    /** Metric type prefix for all Culvert custom metrics. */
    static final String METRIC_PREFIX = "custom.googleapis.com/culvert/";

    /** Full metric type for rows_processed (CUMULATIVE INT64). */
    static final String METRIC_ROWS_PROCESSED = METRIC_PREFIX + "rows_processed";

    /** Full metric type for stage_latency_ms (GAUGE DOUBLE). */
    static final String METRIC_STAGE_LATENCY_MS = METRIC_PREFIX + "stage_latency_ms";

    /** Full metric type for error_count (CUMULATIVE INT64). */
    static final String METRIC_ERROR_COUNT = METRIC_PREFIX + "error_count";

    private final MetricServiceClient client;
    private final String projectId;
    private final AtomicLong monitoringFailures = new AtomicLong();

    /** System property key for the GCP project override. */
    static final String SYSPROP_GCP_PROJECT = "culvert.gcp.project";

    /** Environment variable key for the GCP project override. */
    static final String ENVVAR_GCP_PROJECT = "CULVERT_GCP_PROJECT";

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery (T12.6).
     *
     * <p>Resolves the GCP project-id from the following precedence chain:
     * <ol>
     *   <li>System property {@value #SYSPROP_GCP_PROJECT}</li>
     *   <li>Environment variable {@value #ENVVAR_GCP_PROJECT}</li>
     *   <li>ADC default: {@code com.google.cloud.ServiceOptions.getDefaultProjectId()}</li>
     * </ol>
     * Throws {@link IllegalStateException} if none of the three yields a non-blank value.
     *
     * <p>Builds the {@link MetricServiceClient} via its {@code create()} factory, which
     * picks up Application Default Credentials from the environment. This is the expected
     * mode on a Dataflow worker where ADC is always present.
     *
     * <p>Mirrors the {@code GcsBlobStore()} no-arg pattern: same "ADC + no-arg = ServiceLoader
     * entry point" shape, extended to also resolve project-id from config.
     *
     * @throws IllegalStateException if no GCP project-id is resolvable from any source.
     * @throws RuntimeException wrapping {@link IOException} if {@code MetricServiceClient.create()}
     *         fails (e.g. credentials unavailable — expected only when ADC is absent).
     */
    public CloudMonitoringMetricsHook() {
        this(createDefaultClient(), resolveProjectId());
    }

    /**
     * Explicit constructor for tests and custom-credential wiring.
     *
     * @param client    Pre-built Cloud Monitoring client. Required. Ownership
     *                  transfers to this hook — {@link #close()} will close it.
     * @param projectId GCP project ID to which time series are written. Required.
     * @throws NullPointerException if either argument is null.
     */
    public CloudMonitoringMetricsHook(MetricServiceClient client, String projectId) {
        this.client    = Objects.requireNonNull(client,    "client must not be null");
        this.projectId = Objects.requireNonNull(projectId, "projectId must not be null");
    }

    /**
     * Resolves the GCP project-id using the three-step precedence chain.
     *
     * <p>Package-private for testing (allows tests to verify resolution without
     * needing to mock static state — the property branch is testable via
     * {@link System#setProperty}).
     *
     * @return non-blank project-id string
     * @throws IllegalStateException if all three sources are null or blank
     */
    static String resolveProjectId() {
        // 1. System property (testable via System.setProperty, highest priority)
        String fromProp = System.getProperty(SYSPROP_GCP_PROJECT);
        if (fromProp != null && !fromProp.isBlank()) {
            return fromProp;
        }
        // 2. Environment variable (set by Dataflow worker environment / k8s / Cloud Run)
        String fromEnv = System.getenv(ENVVAR_GCP_PROJECT);
        if (fromEnv != null && !fromEnv.isBlank()) {
            return fromEnv;
        }
        // 3. ADC default project (resolves from gcloud auth, service account, metadata server)
        String fromAdc = com.google.cloud.ServiceOptions.getDefaultProjectId();
        if (fromAdc != null && !fromAdc.isBlank()) {
            return fromAdc;
        }
        throw new IllegalStateException(
                "Cannot resolve GCP project-id for CloudMonitoringMetricsHook. "
                + "Set one of: system property '" + SYSPROP_GCP_PROJECT + "', "
                + "environment variable '" + ENVVAR_GCP_PROJECT + "', "
                + "or configure Application Default Credentials with a default project "
                + "(gcloud config set project <PROJECT_ID>).");
    }

    /**
     * Builds a {@link MetricServiceClient} using Application Default Credentials.
     *
     * <p>Package-private so tests can verify no-arg construction without a real GCP
     * project. The {@code MetricServiceClient.create()} call is wrapped here so the
     * checked {@link IOException} is translated to an unchecked {@link RuntimeException}.
     *
     * @throws RuntimeException wrapping {@link IOException} if client creation fails
     */
    static MetricServiceClient createDefaultClient() {
        try {
            return MetricServiceClient.create();
        } catch (IOException e) {
            throw new RuntimeException(
                    "Failed to create MetricServiceClient from Application Default Credentials. "
                    + "Ensure ADC is configured (GOOGLE_APPLICATION_CREDENTIALS env var, "
                    + "gcloud auth application-default login, or a service account on the "
                    + "Dataflow worker).", e);
        }
    }

    /**
     * Emit all three Culvert metrics for a completed stage to Cloud Monitoring.
     *
     * <p>A single {@code CreateTimeSeries} RPC carries all three
     * {@link TimeSeries} objects. If the RPC fails the exception is logged and
     * swallowed — monitoring failures never interrupt the pipeline.
     *
     * @param metrics Stage metrics snapshot. Must not be null.
     */
    @Override
    public void recordStageMetrics(StageMetrics metrics) {
        Objects.requireNonNull(metrics, "metrics must not be null");

        Instant now = Instant.now();
        Instant start = now.minusMillis(Math.round(metrics.stageLatencyMs()));

        com.google.protobuf.Timestamp endTs   = toProtoTimestamp(now);
        com.google.protobuf.Timestamp startTs = toProtoTimestamp(start);

        MonitoredResource resource = MonitoredResource.newBuilder()
                .setType("global")
                .putLabels("project_id", projectId)
                .build();

        TimeSeries rowsSeries   = buildCumulativeInt64(METRIC_ROWS_PROCESSED,
                metrics, resource, startTs, endTs, metrics.rowsProcessed());
        TimeSeries latencySeries = buildGaugeDouble(METRIC_STAGE_LATENCY_MS,
                metrics, resource, endTs, metrics.stageLatencyMs());
        TimeSeries errorSeries  = buildCumulativeInt64(METRIC_ERROR_COUNT,
                metrics, resource, startTs, endTs, metrics.errorCount());

        CreateTimeSeriesRequest request = CreateTimeSeriesRequest.newBuilder()
                .setName(ProjectName.of(projectId).toString())
                .addAllTimeSeries(List.of(rowsSeries, latencySeries, errorSeries))
                .build();

        try {
            client.createTimeSeries(request);
        } catch (Exception ex) {
            monitoringFailures.incrementAndGet();
            LOG.warn("CloudMonitoringMetricsHook: failed to write metrics for "
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

    /** GCP project ID this hook emits to. */
    public String projectId() {
        return projectId;
    }

    @Override
    public void close() {
        client.close();
    }

    // --- helpers -------------------------------------------------------------

    private static TimeSeries buildCumulativeInt64(
            String metricType,
            StageMetrics metrics,
            MonitoredResource resource,
            com.google.protobuf.Timestamp startTs,
            com.google.protobuf.Timestamp endTs,
            long value) {

        TimeInterval interval = TimeInterval.newBuilder()
                .setStartTime(startTs)
                .setEndTime(endTs)
                .build();

        Point point = Point.newBuilder()
                .setInterval(interval)
                .setValue(TypedValue.newBuilder().setInt64Value(value).build())
                .build();

        return TimeSeries.newBuilder()
                .setMetric(buildMetric(metricType, metrics))
                .setResource(resource)
                .setMetricKind(MetricDescriptor.MetricKind.CUMULATIVE)
                .setValueType(MetricDescriptor.ValueType.INT64)
                .addPoints(point)
                .build();
    }

    private static TimeSeries buildGaugeDouble(
            String metricType,
            StageMetrics metrics,
            MonitoredResource resource,
            com.google.protobuf.Timestamp endTs,
            double value) {

        TimeInterval interval = TimeInterval.newBuilder()
                .setEndTime(endTs)
                .build();

        Point point = Point.newBuilder()
                .setInterval(interval)
                .setValue(TypedValue.newBuilder().setDoubleValue(value).build())
                .build();

        return TimeSeries.newBuilder()
                .setMetric(buildMetric(metricType, metrics))
                .setResource(resource)
                .setMetricKind(MetricDescriptor.MetricKind.GAUGE)
                .setValueType(MetricDescriptor.ValueType.DOUBLE)
                .addPoints(point)
                .build();
    }

    private static com.google.api.Metric buildMetric(String metricType, StageMetrics metrics) {
        return com.google.api.Metric.newBuilder()
                .setType(metricType)
                .putLabels("pipeline_id", metrics.pipelineId())
                .putLabels("run_id",      metrics.runId())
                .putLabels("stage_name",  metrics.stageName())
                .build();
    }

    private static com.google.protobuf.Timestamp toProtoTimestamp(Instant instant) {
        return Timestamps.fromMillis(instant.toEpochMilli());
    }
}

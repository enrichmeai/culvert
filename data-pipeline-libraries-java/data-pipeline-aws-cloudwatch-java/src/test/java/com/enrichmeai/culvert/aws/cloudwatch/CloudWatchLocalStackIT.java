package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.StageMetrics;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.containers.localstack.LocalStackContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.ListMetricsRequest;
import software.amazon.awssdk.services.cloudwatch.model.ListMetricsResponse;
import software.amazon.awssdk.services.cloudwatch.model.Metric;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for {@link CloudWatchObservabilityHook} and {@link
 * CloudWatchStageMetricsHook} exercised against a real CloudWatch {@code
 * PutMetricData}/{@code ListMetrics} API via Testcontainers'
 * {@link LocalStackContainer} (CloudWatch has no dedicated Testcontainers
 * module; LocalStack's generic {@code CLOUDWATCH} service is the standard
 * stand-in for AWS services in this ecosystem, same pattern as
 * {@code SqsLocalStackIT} / {@code DynamoDbJobControlRepositoryTest}'s AWS
 * siblings).
 *
 * <p>LocalStack's community edition accepts {@code PutMetricData} calls and
 * makes the published metric names discoverable via {@code ListMetrics}
 * (metric values / statistics retrieval via {@code GetMetricStatistics} is a
 * Pro-tier feature in some LocalStack editions, so this test intentionally
 * asserts on metric name/namespace/dimension presence via {@code
 * ListMetrics} rather than round-tripping datapoint values).
 *
 * <p><strong>Not run as part of the default build.</strong> Runs only under
 * the parent's {@code it} profile ({@code mvn -P it verify}) via failsafe,
 * and requires a running Docker daemon. Per T21.6 instructions, this IT is
 * not executed as part of this ticket's verification.
 *
 * <p>Sprint-21 deliverable (T21.6, epic #144, issue #150).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class CloudWatchLocalStackIT {

    private static final DockerImageName LOCALSTACK_IMAGE =
            DockerImageName.parse("localstack/localstack:3.4.0");

    private static final String NAMESPACE = "CulvertIT";

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(LOCALSTACK_IMAGE)
                    .withServices(LocalStackContainer.Service.CLOUDWATCH);

    private CloudWatchClient client;
    private CloudWatchObservabilityHook observabilityHook;
    private CloudWatchStageMetricsHook stageMetricsHook;

    @BeforeAll
    void setUp() {
        client = CloudWatchClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(LocalStackContainer.Service.CLOUDWATCH))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(
                                LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();

        // Each hook wraps its own client-owning-nothing view; both share the
        // single underlying CloudWatchClient built above by constructing a
        // fresh (non-owning at the wrapper-doesn't-matter level, but since
        // both close() would double-close the shared client, only one is
        // closed in tearDown — same pattern as SqsLocalStackIT.
        observabilityHook = new CloudWatchObservabilityHook(client, NAMESPACE);
        stageMetricsHook = new CloudWatchStageMetricsHook(
                CloudWatchClient.builder()
                        .endpointOverride(LOCALSTACK.getEndpointOverride(LocalStackContainer.Service.CLOUDWATCH))
                        .region(Region.of(LOCALSTACK.getRegion()))
                        .credentialsProvider(StaticCredentialsProvider.create(
                                AwsBasicCredentials.create(
                                        LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                        .build(),
                NAMESPACE);
    }

    @AfterAll
    void tearDown() {
        if (observabilityHook != null) {
            observabilityHook.close();
        }
        if (stageMetricsHook != null) {
            stageMetricsHook.close();
        }
    }

    private List<Metric> listMetrics() {
        ListMetricsResponse response = client.listMetrics(
                ListMetricsRequest.builder().namespace(NAMESPACE).build());
        return response.metrics();
    }

    private void awaitMetric(String metricName) {
        // LocalStack ingests PutMetricData asynchronously; ListMetrics may lag
        // by a moment. Poll briefly rather than sleeping a fixed duration.
        long deadline = System.nanoTime() + Duration.ofSeconds(15).toNanos();
        while (System.nanoTime() < deadline) {
            boolean found = listMetrics().stream().anyMatch(m -> m.metricName().equals(metricName));
            if (found) {
                return;
            }
            try {
                Thread.sleep(250);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            }
        }
    }

    @Test
    void stageMetricsHookPublishesAllThreeCulvertMetrics() {
        stageMetricsHook.recordStageMetrics(
                new StageMetrics("pipeline-it", "run-it", "load", 42L, 99.0, 1L));

        awaitMetric("culvert/rows_processed");
        awaitMetric("culvert/stage_latency_ms");
        awaitMetric("culvert/error_count");

        List<Metric> metrics = listMetrics();
        assertThat(metrics).extracting(Metric::metricName).contains(
                "culvert/rows_processed", "culvert/stage_latency_ms", "culvert/error_count");

        Metric rows = metrics.stream()
                .filter(m -> m.metricName().equals("culvert/rows_processed"))
                .findFirst()
                .orElseThrow();
        assertThat(rows.dimensions()).extracting(d -> Map.entry(d.name(), d.value()))
                .contains(
                        Map.entry("pipeline_id", "pipeline-it"),
                        Map.entry("run_id", "run-it"),
                        Map.entry("stage_name", "load"));
    }

    @Test
    void observabilityHookCounterAndSpanPublishRealMetrics() {
        observabilityHook.counter("it.records.read", 7, Map.of("stage", "it-ingest"));
        try (ObservabilityHook.Span span = observabilityHook.span("it.stage.transform")) {
            span.setAttribute("stage", "it-transform");
        }

        awaitMetric("it.records.read");
        awaitMetric("it.stage.transform.duration_ms");

        List<Metric> metrics = listMetrics();
        assertThat(metrics).extracting(Metric::metricName)
                .contains("it.records.read", "it.stage.transform.duration_ms");
    }
}

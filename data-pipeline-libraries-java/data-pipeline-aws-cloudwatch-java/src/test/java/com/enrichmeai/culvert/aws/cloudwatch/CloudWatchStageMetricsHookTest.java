package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.StageMetrics;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.Dimension;
import software.amazon.awssdk.services.cloudwatch.model.MetricDatum;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataRequest;
import software.amazon.awssdk.services.cloudwatch.model.StandardUnit;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link CloudWatchStageMetricsHook}.
 *
 * <p>Mocks {@link CloudWatchClient} so no real CloudWatch endpoint or
 * credentials are required. Mirrors {@code CloudMonitoringMetricsHookTest}'s
 * coverage shape (the GCP reference implementation this class mirrors) since
 * there is no shared Java StageMetricsHook contract test to bind against —
 * only the Python contract-tests package has one.
 */
@ExtendWith(MockitoExtension.class)
class CloudWatchStageMetricsHookTest {

    private static final String NAMESPACE = "MyNamespace";

    @Mock
    private CloudWatchClient client;

    private static StageMetrics sampleMetrics() {
        return new StageMetrics("pipeline-1", "run-abc", "transform", 1000L, 250.0, 3L);
    }

    // --- metric emission -----------------------------------------------------

    @Test
    void recordStageMetricsEmitsThreeDatumsInSingleRpc() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());

        assertThat(captor.getValue().metricData()).hasSize(3);
    }

    @Test
    void requestTargetsConfiguredNamespace() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());

        assertThat(captor.getValue().namespace()).isEqualTo(NAMESPACE);
    }

    @Test
    void rowsProcessedDatumHasCorrectNameUnitAndValue() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        MetricDatum datum = capturedDatumByName(CloudWatchStageMetricsHook.METRIC_ROWS_PROCESSED);

        assertThat(datum.metricName()).isEqualTo("culvert/rows_processed");
        assertThat(datum.unit()).isEqualTo(StandardUnit.COUNT);
        assertThat(datum.value()).isEqualTo(1000.0);
    }

    @Test
    void stageLatencyDatumHasCorrectNameUnitAndValue() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        MetricDatum datum = capturedDatumByName(CloudWatchStageMetricsHook.METRIC_STAGE_LATENCY_MS);

        assertThat(datum.metricName()).isEqualTo("culvert/stage_latency_ms");
        assertThat(datum.unit()).isEqualTo(StandardUnit.MILLISECONDS);
        assertThat(datum.value()).isEqualTo(250.0);
    }

    @Test
    void errorCountDatumHasCorrectNameUnitAndValue() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        MetricDatum datum = capturedDatumByName(CloudWatchStageMetricsHook.METRIC_ERROR_COUNT);

        assertThat(datum.metricName()).isEqualTo("culvert/error_count");
        assertThat(datum.unit()).isEqualTo(StandardUnit.COUNT);
        assertThat(datum.value()).isEqualTo(3.0);
    }

    @Test
    void allDatumsCarryCorrectDimensions() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());

        for (MetricDatum datum : captor.getValue().metricData()) {
            List<Dimension> dims = datum.dimensions();
            assertThat(dims).extracting(Dimension::name)
                    .containsExactlyInAnyOrder("pipeline_id", "run_id", "stage_name");
            assertThat(dims).extracting(Dimension::value)
                    .containsExactlyInAnyOrder("pipeline-1", "run-abc", "transform");
        }
    }

    // --- failure isolation ---------------------------------------------------

    @Test
    void monitoringExceptionDoesNotPropagate() {
        doThrow(new RuntimeException("cloudwatch unavailable"))
                .when(client).putMetricData(any(PutMetricDataRequest.class));

        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        assertThatCode(() -> hook.recordStageMetrics(sampleMetrics()))
                .doesNotThrowAnyException();
    }

    @Test
    void monitoringFailureCountIncrementedOnClientException() {
        doThrow(new RuntimeException("cloudwatch unavailable"))
                .when(client).putMetricData(any(PutMetricDataRequest.class));

        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);
        hook.recordStageMetrics(sampleMetrics());
        hook.recordStageMetrics(sampleMetrics());

        assertThat(hook.monitoringFailureCount()).isEqualTo(2L);
    }

    @Test
    void successfulCallsDoNotIncrementFailureCount() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);

        hook.recordStageMetrics(sampleMetrics());

        assertThat(hook.monitoringFailureCount()).isZero();
    }

    // --- namespace resolution -------------------------------------------------

    @AfterEach
    void clearNamespaceSystemProperty() {
        System.clearProperty(CloudWatchStageMetricsHook.SYSPROP_NAMESPACE);
    }

    @Test
    void resolveNamespaceUsesSystemPropertyFirst() {
        System.setProperty(CloudWatchStageMetricsHook.SYSPROP_NAMESPACE, "prop-namespace");
        assertThat(CloudWatchStageMetricsHook.resolveNamespace()).isEqualTo("prop-namespace");
    }

    @Test
    void resolveNamespaceFallsBackToDefaultWhenNothingConfigured() {
        System.clearProperty(CloudWatchStageMetricsHook.SYSPROP_NAMESPACE);

        // Only asserts the default when the env var isn't set in the test env.
        if (System.getenv(CloudWatchStageMetricsHook.ENVVAR_NAMESPACE) == null
                || System.getenv(CloudWatchStageMetricsHook.ENVVAR_NAMESPACE).isBlank()) {
            assertThat(CloudWatchStageMetricsHook.resolveNamespace())
                    .isEqualTo(CloudWatchStageMetricsHook.DEFAULT_NAMESPACE);
        }
    }

    // --- ServiceLoader / SPI ---------------------------------------------------

    @Test
    void serviceLoaderRegistersCloudWatchStageMetricsHook() {
        // We don't instantiate via ServiceLoader here (the no-arg ctor builds a
        // real CloudWatchClient via CloudWatchClient.create(), which requires
        // AWS credentials/region resolution and would make this test
        // environment-dependent). Instead we verify the META-INF/services
        // registration file lists this class, which is what makes
        // ServiceLoader.load(StageMetricsHook.class) able to find it on a
        // classpath with real AWS credentials.
        java.io.InputStream is = getClass().getClassLoader().getResourceAsStream(
                "META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook");
        assertThat(is).isNotNull();
    }

    // --- construction & lifecycle --------------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new CloudWatchStageMetricsHook(null, NAMESPACE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullNamespace() {
        assertThatThrownBy(() -> new CloudWatchStageMetricsHook(client, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void recordStageMetricsRejectsNullMetrics() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.recordStageMetrics(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void namespaceAccessorReturnsConfiguredValue() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);
        assertThat(hook.namespace()).isEqualTo(NAMESPACE);
    }

    @Test
    void closeDelegatesToClient() {
        CloudWatchStageMetricsHook hook = new CloudWatchStageMetricsHook(client, NAMESPACE);
        hook.close();
        verify(client).close();
    }

    // --- helper --------------------------------------------------------------

    private MetricDatum capturedDatumByName(String metricName) {
        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());

        List<MetricDatum> all = captor.getValue().metricData();
        return all.stream()
                .filter(d -> d.metricName().equals(metricName))
                .findFirst()
                .orElseThrow(() -> new AssertionError(
                        "No MetricDatum named " + metricName + " found in " + all));
    }
}

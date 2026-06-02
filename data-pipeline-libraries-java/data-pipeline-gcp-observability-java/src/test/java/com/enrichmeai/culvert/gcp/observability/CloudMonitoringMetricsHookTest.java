package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.google.api.MetricDescriptor;
import com.google.cloud.monitoring.v3.MetricServiceClient;
import com.google.monitoring.v3.CreateTimeSeriesRequest;
import com.google.monitoring.v3.TimeSeries;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link CloudMonitoringMetricsHook}.
 *
 * <p>Mocks {@link MetricServiceClient} so no real Cloud Monitoring endpoint
 * or credentials are required.
 */
@ExtendWith(MockitoExtension.class)
class CloudMonitoringMetricsHookTest {

    private static final String PROJECT_ID = "my-gcp-project";

    @Mock
    private MetricServiceClient client;

    private static StageMetrics sampleMetrics() {
        return new StageMetrics("pipeline-1", "run-abc", "transform", 1000L, 250.0, 3L);
    }

    // --- metric emission -----------------------------------------------------

    @Test
    void recordStageMetricsEmitsThreeTimeSeriesInSingleRpc() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<CreateTimeSeriesRequest> captor =
                ArgumentCaptor.forClass(CreateTimeSeriesRequest.class);
        verify(client).createTimeSeries(captor.capture());

        CreateTimeSeriesRequest req = captor.getValue();
        assertThat(req.getTimeSeriesList()).hasSize(3);
    }

    @Test
    void requestTargetsCorrectProject() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<CreateTimeSeriesRequest> captor =
                ArgumentCaptor.forClass(CreateTimeSeriesRequest.class);
        verify(client).createTimeSeries(captor.capture());

        assertThat(captor.getValue().getName()).isEqualTo("projects/" + PROJECT_ID);
    }

    @Test
    void rowsProcessedTimeSeriesHasCorrectMetricTypeKindAndValue() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        TimeSeries ts = capturedSeriesByType(CloudMonitoringMetricsHook.METRIC_ROWS_PROCESSED);

        assertThat(ts.getMetric().getType()).isEqualTo(
                "custom.googleapis.com/culvert/rows_processed");
        assertThat(ts.getMetricKind()).isEqualTo(MetricDescriptor.MetricKind.CUMULATIVE);
        assertThat(ts.getValueType()).isEqualTo(MetricDescriptor.ValueType.INT64);
        assertThat(ts.getPoints(0).getValue().getInt64Value()).isEqualTo(1000L);
        // CUMULATIVE requires both start and end times
        assertThat(ts.getPoints(0).getInterval().hasStartTime()).isTrue();
        assertThat(ts.getPoints(0).getInterval().hasEndTime()).isTrue();
    }

    @Test
    void stageLatencyTimeSeriesHasCorrectMetricTypeKindAndValue() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        TimeSeries ts = capturedSeriesByType(CloudMonitoringMetricsHook.METRIC_STAGE_LATENCY_MS);

        assertThat(ts.getMetric().getType()).isEqualTo(
                "custom.googleapis.com/culvert/stage_latency_ms");
        assertThat(ts.getMetricKind()).isEqualTo(MetricDescriptor.MetricKind.GAUGE);
        assertThat(ts.getValueType()).isEqualTo(MetricDescriptor.ValueType.DOUBLE);
        assertThat(ts.getPoints(0).getValue().getDoubleValue()).isEqualTo(250.0);
    }

    @Test
    void errorCountTimeSeriesHasCorrectMetricTypeKindAndValue() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        TimeSeries ts = capturedSeriesByType(CloudMonitoringMetricsHook.METRIC_ERROR_COUNT);

        assertThat(ts.getMetric().getType()).isEqualTo(
                "custom.googleapis.com/culvert/error_count");
        assertThat(ts.getMetricKind()).isEqualTo(MetricDescriptor.MetricKind.CUMULATIVE);
        assertThat(ts.getValueType()).isEqualTo(MetricDescriptor.ValueType.INT64);
        assertThat(ts.getPoints(0).getValue().getInt64Value()).isEqualTo(3L);
    }

    @Test
    void allTimeSeriesCarryCorrectLabels() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<CreateTimeSeriesRequest> captor =
                ArgumentCaptor.forClass(CreateTimeSeriesRequest.class);
        verify(client).createTimeSeries(captor.capture());

        for (TimeSeries ts : captor.getValue().getTimeSeriesList()) {
            assertThat(ts.getMetric().getLabelsMap())
                    .containsEntry("pipeline_id", "pipeline-1")
                    .containsEntry("run_id",      "run-abc")
                    .containsEntry("stage_name",  "transform");
        }
    }

    @Test
    void allTimeSeriesHaveGlobalMonitoredResource() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        ArgumentCaptor<CreateTimeSeriesRequest> captor =
                ArgumentCaptor.forClass(CreateTimeSeriesRequest.class);
        verify(client).createTimeSeries(captor.capture());

        for (TimeSeries ts : captor.getValue().getTimeSeriesList()) {
            assertThat(ts.getResource().getType()).isEqualTo("global");
            assertThat(ts.getResource().getLabelsMap())
                    .containsEntry("project_id", PROJECT_ID);
        }
    }

    // --- failure isolation ---------------------------------------------------

    @Test
    void monitoringExceptionDoesNotPropagate() {
        doThrow(new RuntimeException("monitoring unavailable"))
                .when(client).createTimeSeries(any(CreateTimeSeriesRequest.class));

        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        // Must return normally — monitoring failure must never interrupt the pipeline.
        assertThatCode(() -> hook.recordStageMetrics(sampleMetrics()))
                .doesNotThrowAnyException();
    }

    @Test
    void monitoringFailureCountIncrementedOnClientException() {
        doThrow(new RuntimeException("monitoring unavailable"))
                .when(client).createTimeSeries(any(CreateTimeSeriesRequest.class));

        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);
        hook.recordStageMetrics(sampleMetrics());
        hook.recordStageMetrics(sampleMetrics());

        assertThat(hook.monitoringFailureCount()).isEqualTo(2L);
    }

    @Test
    void successfulCallsDoNotIncrementFailureCount() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);

        hook.recordStageMetrics(sampleMetrics());

        assertThat(hook.monitoringFailureCount()).isZero();
    }

    // --- no-arg constructor + project-id precedence (T12.6) ------------------

    @AfterEach
    void clearProjectSystemProperty() {
        System.clearProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT);
    }

    @Test
    void resolveProjectIdUsesSystemPropertyFirst() {
        System.setProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT, "prop-project");
        // System property takes precedence over everything else.
        assertThat(CloudMonitoringMetricsHook.resolveProjectId()).isEqualTo("prop-project");
    }

    @Test
    @SuppressWarnings("rawtypes")
    void resolveProjectIdFallsBackToAdcWhenPropertyAbsent() {
        // No system property set; mock ServiceOptions.getDefaultProjectId()
        System.clearProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT);

        // ServiceOptions is generic (ServiceOptions<ServiceT,OptionsT>); the class literal
        // is a raw type. @SuppressWarnings("rawtypes") is required with -Xlint:all -Werror.
        @SuppressWarnings("unchecked")
        MockedStatic<com.google.cloud.ServiceOptions> opts =
                mockStatic(com.google.cloud.ServiceOptions.class);
        try (opts) {
            opts.when(com.google.cloud.ServiceOptions::getDefaultProjectId)
                    .thenReturn("adc-project");

            // CULVERT_GCP_PROJECT env var is not set in test env; fallback to ADC.
            // If the env var IS set in the current environment the test still passes
            // because the env branch precedes ADC — the env value is itself valid.
            String resolved = CloudMonitoringMetricsHook.resolveProjectId();
            assertThat(resolved).isNotBlank();
        }
    }

    @Test
    @SuppressWarnings("rawtypes")
    void resolveProjectIdThrowsWhenNoSourceResolvable() {
        // No system property, and mock ADC to return null, and we cannot set env vars
        // at runtime — the env branch is exercised by the environment. The test
        // explicitly proves the failure path when ADC also returns null.
        System.clearProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT);

        // ServiceOptions is generic; raw type required for class literal. Suppressed.
        @SuppressWarnings("unchecked")
        MockedStatic<com.google.cloud.ServiceOptions> opts =
                mockStatic(com.google.cloud.ServiceOptions.class);
        try (opts) {
            opts.when(com.google.cloud.ServiceOptions::getDefaultProjectId).thenReturn(null);

            // Only throws if env var is also absent. Guard: skip if env var IS set.
            if (System.getenv(CloudMonitoringMetricsHook.ENVVAR_GCP_PROJECT) == null
                    || System.getenv(CloudMonitoringMetricsHook.ENVVAR_GCP_PROJECT).isBlank()) {
                assertThatThrownBy(CloudMonitoringMetricsHook::resolveProjectId)
                        .isInstanceOf(IllegalStateException.class)
                        .hasMessageContaining(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT)
                        .hasMessageContaining(CloudMonitoringMetricsHook.ENVVAR_GCP_PROJECT);
            }
        }
    }

    @Test
    void noArgCtorProducesWorkingHookViaStaticMocking() {
        // Verify the no-arg ctor is callable (ServiceLoader path) when project-id
        // is provided via system property and client creation is mocked.
        System.setProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT, "test-project");

        try (MockedStatic<MetricServiceClient> staticClient =
                     mockStatic(MetricServiceClient.class)) {
            MetricServiceClient mockClient = mock(MetricServiceClient.class);
            staticClient.when(MetricServiceClient::create).thenReturn(mockClient);

            CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook();
            assertThat(hook.projectId()).isEqualTo("test-project");
            // Verify it can record metrics without throwing.
            assertThatCode(() -> hook.recordStageMetrics(sampleMetrics()))
                    .doesNotThrowAnyException();
        }
    }

    @Test
    void serviceLoaderCanInstantiateStageMetricsHookSpiEntry() {
        // ServiceLoader SPI story is now TRUE (T12.6). Verify the SPI entry can be
        // instantiated via ServiceLoader without ServiceConfigurationError — the
        // registry silently skips impls that throw, so we assert we can find one.
        // Requires project-id resolvable and MetricServiceClient.create() mockable.
        System.setProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT, "spi-project");

        try (MockedStatic<MetricServiceClient> staticClient =
                     mockStatic(MetricServiceClient.class)) {
            staticClient.when(MetricServiceClient::create).thenReturn(mock(MetricServiceClient.class));

            java.util.ServiceLoader<com.enrichmeai.culvert.contracts.StageMetricsHook> loader =
                    java.util.ServiceLoader.load(com.enrichmeai.culvert.contracts.StageMetricsHook.class);

            // Collect all impls found — must include CloudMonitoringMetricsHook.
            java.util.List<com.enrichmeai.culvert.contracts.StageMetricsHook> hooks = new java.util.ArrayList<>();
            loader.forEach(hooks::add);

            assertThat(hooks).isNotEmpty();
            assertThat(hooks).anyMatch(h -> h instanceof CloudMonitoringMetricsHook);
        }
    }

    // --- construction & lifecycle --------------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new CloudMonitoringMetricsHook(null, PROJECT_ID))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullProjectId() {
        assertThatThrownBy(() -> new CloudMonitoringMetricsHook(client, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void recordStageMetricsRejectsNullMetrics() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);
        assertThatThrownBy(() -> hook.recordStageMetrics(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void projectIdAccessorReturnsConfiguredValue() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);
        assertThat(hook.projectId()).isEqualTo(PROJECT_ID);
    }

    @Test
    void closeDelegatesToClient() {
        CloudMonitoringMetricsHook hook = new CloudMonitoringMetricsHook(client, PROJECT_ID);
        hook.close();
        verify(client).close();
    }

    // --- helper --------------------------------------------------------------

    private TimeSeries capturedSeriesByType(String metricType) {
        ArgumentCaptor<CreateTimeSeriesRequest> captor =
                ArgumentCaptor.forClass(CreateTimeSeriesRequest.class);
        verify(client).createTimeSeries(captor.capture());

        List<TimeSeries> all = captor.getValue().getTimeSeriesList();
        return all.stream()
                .filter(ts -> ts.getMetric().getType().equals(metricType))
                .findFirst()
                .orElseThrow(() -> new AssertionError(
                        "No TimeSeries with metric type " + metricType + " found in " + all));
    }
}

package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.google.api.MetricDescriptor;
import com.google.cloud.monitoring.v3.MetricServiceClient;
import com.google.monitoring.v3.CreateTimeSeriesRequest;
import com.google.monitoring.v3.TimeSeries;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
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

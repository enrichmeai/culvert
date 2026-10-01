package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.contracttests.StageMetricsHookContractTest;
import com.google.cloud.monitoring.v3.MetricServiceClient;
import com.google.monitoring.v3.CreateTimeSeriesRequest;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;

/**
 * {@link CloudMonitoringMetricsHook} against the shared
 * {@link StageMetricsHookContractTest}: a mocked {@link MetricServiceClient}
 * (the seam {@code CloudMonitoringMetricsHookTest} uses) that accepts writes,
 * or throws on every {@code createTimeSeries}.
 */
class CloudMonitoringMetricsHookContractTest extends StageMetricsHookContractTest {

    @Override
    protected StageMetricsHook hook() {
        return new CloudMonitoringMetricsHook(mock(MetricServiceClient.class), "contract-project");
    }

    @Override
    protected StageMetricsHook failingHook() {
        MetricServiceClient client = mock(MetricServiceClient.class);
        doThrow(new IllegalStateException("Cloud Monitoring unavailable"))
                .when(client).createTimeSeries(any(CreateTimeSeriesRequest.class));
        return new CloudMonitoringMetricsHook(client, "contract-project");
    }
}

package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.contracttests.StageMetricsHookContractTest;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataRequest;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link CloudWatchStageMetricsHook} against the shared
 * {@link StageMetricsHookContractTest}: a mocked {@link CloudWatchClient}
 * (the seam {@code CloudWatchStageMetricsHookTest} uses) that accepts writes,
 * or throws on every {@code putMetricData}.
 */
class CloudWatchStageMetricsHookContractTest extends StageMetricsHookContractTest {

    @Override
    protected StageMetricsHook hook() {
        return new CloudWatchStageMetricsHook(mock(CloudWatchClient.class), "ContractTest");
    }

    @Override
    protected StageMetricsHook failingHook() {
        CloudWatchClient client = mock(CloudWatchClient.class);
        when(client.putMetricData(any(PutMetricDataRequest.class)))
                .thenThrow(new IllegalStateException("CloudWatch unavailable"));
        return new CloudWatchStageMetricsHook(client, "ContractTest");
    }
}

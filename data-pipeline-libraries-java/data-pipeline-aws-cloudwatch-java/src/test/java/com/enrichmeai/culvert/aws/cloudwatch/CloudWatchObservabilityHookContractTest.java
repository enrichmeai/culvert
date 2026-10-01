package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracttests.ObservabilityHookContractTest;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.Dimension;
import software.amazon.awssdk.services.cloudwatch.model.MetricDatum;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataRequest;
import software.amazon.awssdk.services.cloudwatch.model.PutMetricDataResponse;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link CloudWatchObservabilityHook} against the shared
 * {@link ObservabilityHookContractTest}.
 *
 * <p>The backend double is a mocked {@link CloudWatchClient} (the seam
 * {@code CloudWatchObservabilityHookTest} uses) that records every
 * {@code MetricDatum} it is sent, with its dimensions as tags. CloudWatch has
 * no trace API: this hook reports a span by putting a {@code <name>.duration_ms}
 * datum on close, with the span's attributes as dimensions. So an ended span,
 * for this backend, is that datum, and those datums are not counted as
 * metrics.
 */
class CloudWatchObservabilityHookContractTest extends ObservabilityHookContractTest {

    private static final String SPAN_SUFFIX = ".duration_ms";
    private static final String EXCEPTION_SUFFIX = ".exception_count";

    private final List<MetricDatum> sent = new ArrayList<>();

    @Override
    protected ObservabilityHook hook() {
        CloudWatchClient client = mock(CloudWatchClient.class);
        when(client.putMetricData(any(PutMetricDataRequest.class))).thenAnswer(inv -> {
            PutMetricDataRequest request = inv.getArgument(0);
            sent.addAll(request.metricData());
            return PutMetricDataResponse.builder().build();
        });
        return new CloudWatchObservabilityHook(client, "ContractTest");
    }

    private static Map<String, String> tags(MetricDatum datum) {
        Map<String, String> tags = new LinkedHashMap<>();
        if (datum.hasDimensions()) {
            for (Dimension dimension : datum.dimensions()) {
                tags.put(dimension.name(), dimension.value());
            }
        }
        return tags;
    }

    @Override
    protected List<Metric> metrics() {
        return sent.stream()
                .filter(d -> !d.metricName().endsWith(SPAN_SUFFIX) && !d.metricName().endsWith(EXCEPTION_SUFFIX))
                .map(d -> new Metric(d.metricName(), d.value(), tags(d)))
                .toList();
    }

    @Override
    protected List<EndedSpan> spans() {
        return sent.stream()
                .filter(d -> d.metricName().endsWith(SPAN_SUFFIX))
                .map(d -> new EndedSpan(
                        d.metricName().substring(0, d.metricName().length() - SPAN_SUFFIX.length()),
                        tags(d)))
                .toList();
    }
}

package com.enrichmeai.culvert.aws.cloudwatch;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
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
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link CloudWatchObservabilityHook}. Mocks {@link
 * CloudWatchClient} so no real CloudWatch endpoint or credentials are
 * required.
 */
@ExtendWith(MockitoExtension.class)
class CloudWatchObservabilityHookTest {

    private static final String NAMESPACE = "MyNamespace";

    @Mock
    private CloudWatchClient client;

    // --- counter ---------------------------------------------------------------

    @Test
    void counterPublishesCountUnitDatum() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.counter("records.read", 5, Map.of("stage", "ingest"));

        MetricDatum datum = capturedSingleDatum();
        assertThat(datum.metricName()).isEqualTo("records.read");
        assertThat(datum.unit()).isEqualTo(StandardUnit.COUNT);
        assertThat(datum.value()).isEqualTo(5.0);
        assertThat(datum.dimensions()).extracting(Dimension::name).containsExactly("stage");
        assertThat(datum.dimensions()).extracting(Dimension::value).containsExactly("ingest");
    }

    @Test
    void counterToleratesNullTagsMap() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.counter("free.counter", 1, null);

        MetricDatum datum = capturedSingleDatum();
        assertThat(datum.dimensions()).isEmpty();
    }

    @Test
    void counterRejectsNullName() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.counter(null, 1, Map.of()))
                .isInstanceOf(NullPointerException.class);
    }

    // --- gauge -------------------------------------------------------------

    @Test
    void gaugePublishesNoneUnitDatum() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.gauge("queue_depth", 17.0, Map.of("stage", "load"));

        MetricDatum datum = capturedSingleDatum();
        assertThat(datum.metricName()).isEqualTo("queue_depth");
        assertThat(datum.unit()).isEqualTo(StandardUnit.NONE);
        assertThat(datum.value()).isEqualTo(17.0);
    }

    @Test
    void gaugeRejectsNullName() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.gauge(null, 1.0, Map.of()))
                .isInstanceOf(NullPointerException.class);
    }

    // --- histogram -----------------------------------------------------------

    @Test
    void histogramPublishesDatumPerObservation() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.histogram("latency_ms", 12.5, Map.of());
        hook.histogram("latency_ms", 42.0, Map.of());

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client, times(2)).putMetricData(captor.capture());

        List<Double> values = captor.getAllValues().stream()
                .flatMap(r -> r.metricData().stream())
                .map(MetricDatum::value)
                .toList();
        assertThat(values).containsExactly(12.5, 42.0);
    }

    @Test
    void histogramRejectsNullName() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.histogram(null, 1.0, Map.of()))
                .isInstanceOf(NullPointerException.class);
    }

    // --- request namespace -----------------------------------------------------

    @Test
    void requestTargetsConfiguredNamespace() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.counter("c", 1, Map.of());

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());
        assertThat(captor.getValue().namespace()).isEqualTo(NAMESPACE);
    }

    // --- log ---------------------------------------------------------------

    @Test
    void logAcceptsAllStandardLevels() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        Map<String, Object> fields = Map.of("run_id", "abc-123");
        hook.log("DEBUG", "d", fields);
        hook.log("INFO", "i", fields);
        hook.log("WARN", "w", fields);
        hook.log("ERROR", "e", fields);
        hook.log("info", "lowercase still routes", fields);
    }

    @Test
    void logRejectsNullLevelOrMessage() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.log(null, "msg", Map.of()))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> hook.log("INFO", null, Map.of()))
                .isInstanceOf(NullPointerException.class);
    }

    // --- span (lightweight timer) --------------------------------------------

    @Test
    void spanClosePublishesDurationDatum() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        try (ObservabilityHook.Span s = hook.span("stage.read")) {
            s.setAttribute("stage", "read");
        }

        MetricDatum datum = capturedSingleDatum();
        assertThat(datum.metricName()).isEqualTo("stage.read.duration_ms");
        assertThat(datum.unit()).isEqualTo(StandardUnit.MILLISECONDS);
        assertThat(datum.dimensions()).extracting(Dimension::name).containsExactly("stage");
        assertThat(datum.dimensions()).extracting(Dimension::value).containsExactly("read");
    }

    @Test
    void spanRecordExceptionAlsoPublishesExceptionCountDatumOnClose() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        ObservabilityHook.Span s = hook.span("stage.transform");
        s.recordException(new RuntimeException("boom"));
        s.close();

        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client, times(2)).putMetricData(captor.capture());

        List<String> names = captor.getAllValues().stream()
                .flatMap(r -> r.metricData().stream())
                .map(MetricDatum::metricName)
                .toList();
        assertThat(names).containsExactlyInAnyOrder(
                "stage.transform.duration_ms", "stage.transform.exception_count");
    }

    @Test
    void spanWithoutExceptionOnlyPublishesDurationDatum() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        ObservabilityHook.Span s = hook.span("stage.write");
        s.close();

        verify(client, times(1)).putMetricData(any(PutMetricDataRequest.class));
    }

    @Test
    void spanCloseIsIdempotent() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        ObservabilityHook.Span s = hook.span("stage.write");
        s.close();
        s.close(); // second close must be a no-op

        verify(client, times(1)).putMetricData(any(PutMetricDataRequest.class));
    }

    @Test
    void spanRejectsNullName() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThatThrownBy(() -> hook.span(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void spanSetAttributeAndRecordExceptionRejectNulls() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        ObservabilityHook.Span s = hook.span("stage.x");
        try {
            assertThatThrownBy(() -> s.setAttribute(null, "v")).isInstanceOf(NullPointerException.class);
            assertThatThrownBy(() -> s.setAttribute("k", null)).isInstanceOf(NullPointerException.class);
            assertThatThrownBy(() -> s.recordException(null)).isInstanceOf(NullPointerException.class);
        } finally {
            s.close();
        }
    }

    // --- failure isolation ---------------------------------------------------

    @Test
    void monitoringExceptionDoesNotPropagate() {
        doThrow(new RuntimeException("cloudwatch unavailable"))
                .when(client).putMetricData(any(PutMetricDataRequest.class));

        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        assertThatCode(() -> hook.counter("c", 1, Map.of())).doesNotThrowAnyException();
    }

    @Test
    void monitoringFailureCountIncrementedOnClientException() {
        doThrow(new RuntimeException("cloudwatch unavailable"))
                .when(client).putMetricData(any(PutMetricDataRequest.class));

        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        hook.counter("c", 1, Map.of());
        hook.gauge("g", 1.0, Map.of());

        assertThat(hook.monitoringFailureCount()).isEqualTo(2L);
    }

    @Test
    void successfulCallsDoNotIncrementFailureCount() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);

        hook.counter("c", 1, Map.of());

        assertThat(hook.monitoringFailureCount()).isZero();
    }

    // --- ServiceLoader / SPI ---------------------------------------------------

    @Test
    void serviceLoaderRegistersCloudWatchObservabilityHook() {
        // Same rationale as CloudWatchStageMetricsHookTest: the no-arg ctor
        // builds a real CloudWatchClient via CloudWatchClient.create(), which
        // needs AWS credentials/region resolution, so we don't instantiate it
        // via ServiceLoader here. We verify the META-INF/services
        // registration file instead.
        java.io.InputStream is = getClass().getClassLoader().getResourceAsStream(
                "META-INF/services/com.enrichmeai.culvert.contracts.ObservabilityHook");
        assertThat(is).isNotNull();
    }

    // --- construction & lifecycle --------------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new CloudWatchObservabilityHook(null, NAMESPACE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullNamespace() {
        assertThatThrownBy(() -> new CloudWatchObservabilityHook(client, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void namespaceAccessorReturnsConfiguredValue() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        assertThat(hook.namespace()).isEqualTo(NAMESPACE);
    }

    @Test
    void closeDelegatesToClient() {
        CloudWatchObservabilityHook hook = new CloudWatchObservabilityHook(client, NAMESPACE);
        hook.close();
        verify(client).close();
    }

    // --- helper --------------------------------------------------------------

    private MetricDatum capturedSingleDatum() {
        ArgumentCaptor<PutMetricDataRequest> captor = ArgumentCaptor.forClass(PutMetricDataRequest.class);
        verify(client).putMetricData(captor.capture());
        assertThat(captor.getValue().metricData()).hasSize(1);
        return captor.getValue().metricData().get(0);
    }
}

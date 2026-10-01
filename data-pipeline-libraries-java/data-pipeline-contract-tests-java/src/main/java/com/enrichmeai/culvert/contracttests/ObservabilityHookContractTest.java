package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link ObservabilityHook} implementation must pass.
 *
 * <p>From the {@link ObservabilityHook} Javadoc:
 * <ul>
 *   <li>{@code counter}, {@code gauge} and {@code histogram} record a named
 *       value with its tags;</li>
 *   <li>{@code log} takes a level, case-insensitive;</li>
 *   <li>a {@link ObservabilityHook.Span} is closed with try-with-resources,
 *       and its attributes annotate it.</li>
 * </ul>
 *
 * <p>Three rules go beyond that Javadoc. They state what every implementation
 * already does, so that a new one cannot quietly differ:
 * <ul>
 *   <li>{@code null} tags or fields mean "none", not an error;</li>
 *   <li>a {@code null} metric or span name is rejected;</li>
 *   <li>closing a span twice ends it once.</li>
 * </ul>
 *
 * <p>The suite does not test what a backend does when it fails: the interface
 * says nothing about that, unlike {@code StageMetricsHook}.
 *
 * <p>Subclasses wire the hook to a backend double and report, in an
 * adapter-neutral shape, what reached it:
 * <ul>
 *   <li>{@link #metrics()}: every metric value the backend received;</li>
 *   <li>{@link #spans()}: every span the backend saw end.</li>
 * </ul>
 */
public abstract class ObservabilityHookContractTest {

    /** A metric value as the backend received it. */
    public record Metric(String name, double value, Map<String, String> tags) {
    }

    /** A span as the backend saw it end, with its attributes. */
    public record EndedSpan(String name, Map<String, String> attributes) {
    }

    protected abstract ObservabilityHook hook();

    protected abstract List<Metric> metrics();

    protected abstract List<EndedSpan> spans();

    private static final Map<String, String> TAGS = Map.of("stage", "load", "env", "test");

    @Test
    void counterRecordsNameValueAndTags() {
        hook().counter("contract.rows", 3, TAGS);
        assertThat(metrics()).containsExactly(new Metric("contract.rows", 3.0, TAGS));
    }

    @Test
    void gaugeRecordsNameValueAndTags() {
        hook().gauge("contract.queue_depth", 7.5, TAGS);
        assertThat(metrics()).containsExactly(new Metric("contract.queue_depth", 7.5, TAGS));
    }

    @Test
    void histogramRecordsNameValueAndTags() {
        hook().histogram("contract.latency_ms", 12.25, TAGS);
        assertThat(metrics()).containsExactly(new Metric("contract.latency_ms", 12.25, TAGS));
    }

    @Test
    void nullOrEmptyTagsMeanNoTags() {
        ObservabilityHook hook = hook();
        hook.counter("contract.a", 1, null);
        hook.gauge("contract.b", 2.0, Map.of());
        hook.histogram("contract.c", 3.0, null);

        assertThat(metrics()).containsExactly(
                new Metric("contract.a", 1.0, Map.of()),
                new Metric("contract.b", 2.0, Map.of()),
                new Metric("contract.c", 3.0, Map.of()));
    }

    @Test
    void nullNamesRejected() {
        ObservabilityHook hook = hook();
        assertThatThrownBy(() -> hook.counter(null, 1, TAGS))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
        assertThatThrownBy(() -> hook.gauge(null, 1.0, TAGS))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
        assertThatThrownBy(() -> hook.histogram(null, 1.0, TAGS))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
        assertThatThrownBy(() -> hook.span(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void logAcceptsEveryLevelInAnyCaseAndNullFields() {
        ObservabilityHook hook = hook();
        Map<String, Object> fields = new HashMap<>();
        fields.put("rows", 3);
        fields.put("stage", "load");
        for (String level : List.of("DEBUG", "INFO", "WARN", "ERROR", "debug", "Info", "warn", "error")) {
            assertThatCode(() -> hook.log(level, "contract message", fields))
                    .as("level %s", level)
                    .doesNotThrowAnyException();
        }
        assertThatCode(() -> hook.log("INFO", "contract message", null)).doesNotThrowAnyException();
    }

    @Test
    void spanEndsOnCloseWithItsAttributes() {
        try (ObservabilityHook.Span span = hook().span("contract.stage")) {
            span.setAttribute("rows", "3");
            span.setAttribute("stage", "load");
        }

        assertThat(spans()).containsExactly(
                new EndedSpan("contract.stage", Map.of("rows", "3", "stage", "load")));
    }

    @Test
    void spanClosedTwiceEndsOnce() {
        ObservabilityHook.Span span = hook().span("contract.stage");
        span.close();
        span.close();

        assertThat(spans()).hasSize(1);
    }

    @Test
    void recordExceptionDoesNotThrowAndTheSpanStillEnds() {
        ObservabilityHook.Span span = hook().span("contract.failing");
        assertThatCode(() -> span.recordException(new IllegalStateException("contract")))
                .doesNotThrowAnyException();
        span.close();

        assertThat(spans()).extracting(EndedSpan::name).containsExactly("contract.failing");
    }
}

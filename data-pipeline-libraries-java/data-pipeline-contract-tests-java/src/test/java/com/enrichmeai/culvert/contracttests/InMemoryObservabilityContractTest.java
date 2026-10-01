package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import org.junit.jupiter.api.Nested;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * The reference: in-memory hooks that pass {@link ObservabilityHookContractTest}
 * and {@link StageMetricsHookContractTest}, so a failure in an adapter's run of
 * the suites is the adapter's, not the suite's.
 */
class InMemoryObservabilityContractTest {

    static final class InMemoryObservabilityHook implements ObservabilityHook {
        final List<ObservabilityHookContractTest.Metric> metrics = new ArrayList<>();
        final List<ObservabilityHookContractTest.EndedSpan> spans = new ArrayList<>();

        private void record(String name, double value, Map<String, String> tags) {
            Objects.requireNonNull(name, "name");
            metrics.add(new ObservabilityHookContractTest.Metric(
                    name, value, tags == null ? Map.of() : Map.copyOf(tags)));
        }

        @Override
        public void counter(String name, long value, Map<String, String> tags) {
            record(name, value, tags);
        }

        @Override
        public void gauge(String name, double value, Map<String, String> tags) {
            record(name, value, tags);
        }

        @Override
        public void histogram(String name, double value, Map<String, String> tags) {
            record(name, value, tags);
        }

        @Override
        public void log(String level, String message, Map<String, Object> fields) {
            Objects.requireNonNull(level, "level");
            Objects.requireNonNull(message, "message");
        }

        @Override
        public Span span(String name) {
            Objects.requireNonNull(name, "name");
            Map<String, String> attributes = new LinkedHashMap<>();
            return new Span() {
                private boolean closed;

                @Override
                public void setAttribute(String key, String value) {
                    attributes.put(key, value);
                }

                @Override
                public void recordException(Throwable t) {
                    Objects.requireNonNull(t, "t");
                }

                @Override
                public void close() {
                    if (!closed) {
                        closed = true;
                        spans.add(new ObservabilityHookContractTest.EndedSpan(name, Map.copyOf(attributes)));
                    }
                }
            };
        }
    }

    /** Records into {@code backend}, swallowing a failure of it as the contract requires. */
    static StageMetricsHook stageMetricsHook(Runnable backend) {
        return metrics -> {
            Objects.requireNonNull(metrics, "metrics");
            try {
                backend.run();
            } catch (RuntimeException swallowed) {
                // A monitoring outage must not stop the pipeline.
            }
        };
    }

    @Nested
    class ObservabilityContract extends ObservabilityHookContractTest {
        private final InMemoryObservabilityHook hook = new InMemoryObservabilityHook();

        @Override
        protected ObservabilityHook hook() {
            return hook;
        }

        @Override
        protected List<Metric> metrics() {
            return hook.metrics;
        }

        @Override
        protected List<EndedSpan> spans() {
            return hook.spans;
        }
    }

    @Nested
    class StageMetricsContract extends StageMetricsHookContractTest {
        @Override
        protected StageMetricsHook hook() {
            return stageMetricsHook(() -> { });
        }

        @Override
        protected StageMetricsHook failingHook() {
            return stageMetricsHook(() -> {
                throw new IllegalStateException("backend down");
            });
        }
    }
}

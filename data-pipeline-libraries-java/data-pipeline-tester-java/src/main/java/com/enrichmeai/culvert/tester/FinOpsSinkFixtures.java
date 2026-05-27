package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;

import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Fixture builders for {@link FinOpsSink}.
 *
 * <p>Unlike the other fixture builders in this module, the capture-sink
 * here is implemented as a real {@link FinOpsSink} (not a Mockito mock) —
 * a tiny direct implementation that appends every {@code record} call to
 * a thread-safe list is simpler and clearer than the Mockito
 * {@code ArgumentCaptor} equivalent.
 *
 * <p>This class is non-instantiable.
 */
public final class FinOpsSinkFixtures {

    private FinOpsSinkFixtures() {
        throw new AssertionError("no instances");
    }

    /**
     * A {@link FinOpsSink} that captures every {@link FinOpsSink#record}
     * call to an in-memory list. Use {@link #records()} to retrieve the
     * captured invocations for assertion.
     *
     * <p>Thread-safe — backed by a {@link CopyOnWriteArrayList} so tests
     * that exercise concurrent record paths don't trip on
     * {@code ConcurrentModificationException}.
     */
    public static final class CaptureSink implements FinOpsSink {

        private final List<Recorded> records = new CopyOnWriteArrayList<>();

        @Override
        public void record(CostMetrics metrics, FinOpsTag tags) {
            Objects.requireNonNull(metrics, "metrics");
            Objects.requireNonNull(tags, "tags");
            records.add(new Recorded(metrics, tags));
        }

        /** Unmodifiable snapshot of every {@code record} call so far. */
        public List<Recorded> records() {
            return Collections.unmodifiableList(records);
        }

        /** Number of {@code record} calls so far. */
        public int recordCount() {
            return records.size();
        }

        /** Clear all captured records. Useful between phases of a long test. */
        public void clear() {
            records.clear();
        }
    }

    /** A single captured {@link FinOpsSink#record} invocation. */
    public record Recorded(CostMetrics metrics, FinOpsTag tags) {
        public Recorded {
            Objects.requireNonNull(metrics, "metrics");
            Objects.requireNonNull(tags, "tags");
        }
    }

    /**
     * Build a {@link CaptureSink} — a real {@link FinOpsSink} that captures
     * each {@code record} call to an in-memory list for later assertion.
     *
     * <p>Example:
     * <pre>{@code
     * CaptureSink sink = FinOpsSinkFixtures.captureSink();
     * pipeline.run(sink);
     * assertThat(sink.records()).hasSize(3);
     * assertThat(sink.records().get(0).metrics().runId()).isEqualTo("run-1");
     * }</pre>
     */
    public static CaptureSink captureSink() {
        return new CaptureSink();
    }

    /**
     * Alias for {@link #captureSink()} — matches the wording in the
     * issue's DoD checklist ("inMemorySink returning a sink that captures
     * records to a List for assertions").
     */
    public static CaptureSink inMemorySink() {
        return captureSink();
    }
}

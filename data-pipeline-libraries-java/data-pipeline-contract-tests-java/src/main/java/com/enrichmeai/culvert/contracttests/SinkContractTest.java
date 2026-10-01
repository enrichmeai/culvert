package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * Contract tests every {@link Sink} implementation must pass.
 *
 * <p>The {@link Sink} Javadoc guarantees ordering only within a single
 * {@code write}. This suite tests the part of that guarantee every reading
 * shares: the sink hands records to its backend in iterator order. Whether the
 * guarantee also covers delivery order is open (#207): Pub/Sub without
 * ordering keys and an SQS standard queue do not deliver in order.
 *
 * <p>The null and close cases go beyond the {@link Sink} Javadoc, which says
 * nothing about either. They state the rule both adapters already follow:
 * a write must never lose a record without saying so. A {@code null} record,
 * a backend that rejects a write, and a write to a closed sink all fail with
 * an exception rather than returning normally. The rule is proposed for
 * {@code docs/CONTRACT.md} in #207.
 *
 * <p>Subclasses wire the sink to a backend double and provide:
 * <ul>
 *   <li>{@link #sink()}: the sink under test. Called once per test.</li>
 *   <li>{@link #sentToBackend()}: every record the backend double has
 *       accepted, in the order it received them.</li>
 *   <li>{@link #record(int)}: a distinct record for each {@code i}.</li>
 *   <li>{@link #backendRejectsWrites()}: make the backend double fail every
 *       write from now on, as a real backend reports a failed publish.</li>
 *   <li>{@link #backendClosed()}: only for a sink that is
 *       {@link AutoCloseable}. The double must refuse writes once closed.</li>
 * </ul>
 */
public abstract class SinkContractTest<U> {

    /** Records per write: more than any backend's batch size (SQS: 10). */
    protected static final int RECORD_COUNT = 25;

    protected abstract Sink<U> sink();

    protected abstract List<U> sentToBackend();

    protected abstract U record(int i);

    protected abstract void backendRejectsWrites();

    /**
     * Whether the backend double has been closed. Only called for a sink that
     * is {@link AutoCloseable}.
     */
    protected boolean backendClosed() {
        throw new UnsupportedOperationException(
                "an AutoCloseable sink's contract test must override backendClosed()");
    }

    /** The context passed to {@code write}. */
    protected RuntimeContext context() {
        return DefaultRuntimeContext.builder("contract-run", "test").build();
    }

    private List<U> records(int count) {
        List<U> records = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            records.add(record(i));
        }
        return records;
    }

    @Test
    void emptyWriteSendsNothing() {
        sink().write(Collections.emptyIterator(), context());
        assertThat(sentToBackend()).isEmpty();
    }

    @Test
    void writeHandsEveryRecordToTheBackendInIteratorOrder() {
        List<U> records = records(RECORD_COUNT);

        sink().write(records.iterator(), context());

        assertThat(sentToBackend()).containsExactlyElementsOf(records);
    }

    @Test
    void nullIteratorRejected() {
        assertThatThrownBy(() -> sink().write(null, context()))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void nullRecordFailsRatherThanBeingDropped() {
        List<U> records = Arrays.asList(record(0), null, record(1));

        assertThatThrownBy(() -> sink().write(records.iterator(), context()))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
        assertThat(sentToBackend()).doesNotContainNull();
    }

    @Test
    void rejectedWriteSurfacesAsAnException() {
        backendRejectsWrites();

        assertThatThrownBy(() -> sink().write(records(3).iterator(), context()))
                .as("a write the backend rejected must not return normally")
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void closeReleasesTheBackend() throws Exception {
        Sink<U> sink = sink();
        assumeTrue(sink instanceof AutoCloseable, "sink is not AutoCloseable");

        ((AutoCloseable) sink).close();

        assertThat(backendClosed()).as("closing the sink closes its backend").isTrue();
    }

    @Test
    void writeAfterCloseFails() throws Exception {
        Sink<U> sink = sink();
        assumeTrue(sink instanceof AutoCloseable, "sink is not AutoCloseable");

        ((AutoCloseable) sink).close();

        assertThatThrownBy(() -> sink.write(records(1).iterator(), context()))
                .as("a closed sink must fail, not drop the record")
                .isInstanceOf(RuntimeException.class);
    }
}

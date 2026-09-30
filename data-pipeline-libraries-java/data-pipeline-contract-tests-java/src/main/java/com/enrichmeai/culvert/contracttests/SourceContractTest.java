package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * Contract tests every {@link Source} implementation must pass.
 *
 * <p>Written from the {@link Source} Javadoc, not from one adapter: {@code read}
 * returns an iterator over the records the backend holds, it never returns
 * {@code null}, and it never yields a {@code null} record. The contract makes
 * no promise about the order in which a backend delivers records, so none is
 * tested here.
 *
 * <p>Subclasses wire the source to a backend double (a mocked client, an
 * in-memory queue) and provide:
 * <ul>
 *   <li>{@link #backlog(List)}: put exactly these records in the backend, so
 *       that the next {@code read} returns them. Called at most once per test,
 *       before {@link #source()}.</li>
 *   <li>{@link #source()}: the source under test. Called once per test.</li>
 *   <li>{@link #record(int)}: a distinct record for each {@code i}.</li>
 *   <li>{@link #backendClosed()}: only for a source that is
 *       {@link AutoCloseable}.</li>
 * </ul>
 *
 * <p>For an {@link AutoCloseable} source, the backend double must refuse calls
 * once it has been closed. The suite then checks that
 * the source lets that failure through: a closed source that returned an empty
 * iterator would be indistinguishable from an empty queue.
 */
public abstract class SourceContractTest<T> {

    /** Records per non-empty backlog: small enough to fit one pull of any backend. */
    protected static final int BACKLOG_SIZE = 3;

    protected abstract Source<T> source();

    protected abstract void backlog(List<T> records);

    protected abstract T record(int i);

    /**
     * Whether the backend double has been closed. Only called for a source that
     * is {@link AutoCloseable}.
     */
    protected boolean backendClosed() {
        throw new UnsupportedOperationException(
                "an AutoCloseable source's contract test must override backendClosed()");
    }

    /** The context passed to {@code read}. */
    protected RuntimeContext context() {
        return DefaultRuntimeContext.builder("contract-run", "test").build();
    }

    private List<T> drain(Iterator<T> iterator) {
        assertThat(iterator).as("read must not return null").isNotNull();
        List<T> records = new ArrayList<>();
        iterator.forEachRemaining(records::add);
        return records;
    }

    @Test
    void emptyBacklogReadsNothing() {
        backlog(List.of());
        assertThat(drain(source().read(context()))).isEmpty();
    }

    @Test
    void readYieldsEachBackloggedRecordOnceAndNoNulls() {
        List<T> backlog = new ArrayList<>();
        for (int i = 0; i < BACKLOG_SIZE; i++) {
            backlog.add(record(i));
        }
        backlog(backlog);

        List<T> read = drain(source().read(context()));

        assertThat(read).doesNotContainNull();
        assertThat(read).containsExactlyInAnyOrderElementsOf(backlog);
    }

    @Test
    void closeReleasesTheBackend() throws Exception {
        Source<T> source = source();
        assumeTrue(source instanceof AutoCloseable, "source is not AutoCloseable");

        ((AutoCloseable) source).close();

        assertThat(backendClosed()).as("closing the source closes its backend").isTrue();
    }

    @Test
    void readAfterCloseFailsRatherThanLookingEmpty() throws Exception {
        Source<T> source = source();
        assumeTrue(source instanceof AutoCloseable, "source is not AutoCloseable");

        ((AutoCloseable) source).close();

        assertThatThrownBy(() -> drain(source.read(context())))
                .as("a closed source must fail, not read as an empty backend")
                .isInstanceOf(RuntimeException.class);
    }
}

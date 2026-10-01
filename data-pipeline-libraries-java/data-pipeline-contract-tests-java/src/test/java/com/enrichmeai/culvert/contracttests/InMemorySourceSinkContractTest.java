package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracts.Source;
import org.junit.jupiter.api.Nested;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;

/**
 * The reference: an in-memory queue that passes {@link SourceContractTest} and
 * {@link SinkContractTest}, so a failure in an adapter's run of the suites is
 * the adapter's, not the suite's.
 */
class InMemorySourceSinkContractTest {

    /** A queue that refuses every call once closed. */
    static final class InMemoryQueue implements AutoCloseable {
        final List<String> messages = new ArrayList<>();
        boolean closed;
        boolean rejecting;

        void checkOpen() {
            if (closed) {
                throw new IllegalStateException("queue is closed");
            }
        }

        @Override
        public void close() {
            closed = true;
        }
    }

    static final class InMemorySource implements Source<String>, AutoCloseable {
        private final InMemoryQueue queue;

        InMemorySource(InMemoryQueue queue) {
            this.queue = queue;
        }

        @Override
        public Iterator<String> read(RuntimeContext context) {
            queue.checkOpen();
            List<String> batch = new ArrayList<>(queue.messages);
            queue.messages.clear();
            return batch.iterator();
        }

        @Override
        public void close() {
            queue.close();
        }
    }

    static final class InMemorySink implements Sink<String>, AutoCloseable {
        private final InMemoryQueue queue;

        InMemorySink(InMemoryQueue queue) {
            this.queue = queue;
        }

        @Override
        public void write(Iterator<String> records, RuntimeContext context) {
            Objects.requireNonNull(records, "records must not be null");
            queue.checkOpen();
            while (records.hasNext()) {
                String record = Objects.requireNonNull(records.next(), "null record");
                if (queue.rejecting) {
                    throw new IllegalStateException("queue rejected the write");
                }
                queue.messages.add(record);
            }
        }

        @Override
        public void close() {
            queue.close();
        }
    }

    @Nested
    class SourceContract extends SourceContractTest<String> {
        private final InMemoryQueue queue = new InMemoryQueue();

        @Override
        protected Source<String> source() {
            return new InMemorySource(queue);
        }

        @Override
        protected void backlog(List<String> records) {
            queue.messages.addAll(records);
        }

        @Override
        protected String record(int i) {
            return "record-" + i;
        }

        @Override
        protected boolean backendClosed() {
            return queue.closed;
        }
    }

    @Nested
    class SinkContract extends SinkContractTest<String> {
        private final InMemoryQueue queue = new InMemoryQueue();

        @Override
        protected Sink<String> sink() {
            return new InMemorySink(queue);
        }

        @Override
        protected List<String> sentToBackend() {
            return queue.messages;
        }

        @Override
        protected String record(int i) {
            return "record-" + i;
        }

        @Override
        protected void backendRejectsWrites() {
            queue.rejecting = true;
        }

        @Override
        protected boolean backendClosed() {
            return queue.closed;
        }
    }
}

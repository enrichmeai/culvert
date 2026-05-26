package com.enrichmeai.culvert;

import com.enrichmeai.culvert.audit.AuditRecord;
import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.SecretProvider;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.enrichmeai.culvert.lineage.LineageEvent;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Demonstrates that simple Java classes can implement the contract
 * interfaces by structural typing — confirming the interfaces are
 * non-trivial and consistent enough to write a minimal in-memory impl
 * against each one.
 *
 * <p>The fakes here are deliberately tiny; Stage 4's contract-test suite
 * is the place for behavioural conformance checks.
 */
class StructuralImplementationTest {

    @Test
    void in_memory_blob_store_implements_interface() {
        BlobStore store = new InMemoryBlobStore();
        store.put("mem://a", "hello".getBytes());
        assertThat(store.exists("mem://a")).isTrue();
        assertThat(new String(store.get("mem://a"))).isEqualTo("hello");
        store.copy("mem://a", "mem://b");
        assertThat(new String(store.get("mem://b"))).isEqualTo("hello");
        store.delete("mem://a");
        assertThat(store.exists("mem://a")).isFalse();
    }

    @Test
    void recording_audit_event_publisher_implements_interface() {
        RecordingAuditPublisher pub = new RecordingAuditPublisher();
        AuditRecord rec = AuditRecord.builder()
                .runId("r1").pipelineName("p").entityType("c")
                .sourceFile("gs://b").recordCount(1)
                .processedTimestamp(Instant.now())
                .processingDurationSeconds(0.1)
                .success(true).build();
        pub.publish(rec);
        pub.flush();
        assertThat(pub.published).hasSize(1);
        assertThat(pub.flushCalls).isEqualTo(1);
    }

    @Test
    void recording_lineage_emitter_implements_interface() {
        RecordingLineageEmitter em = new RecordingLineageEmitter();
        em.emit(LineageEvent.builder().build());
        em.emit(LineageEvent.builder().build());
        assertThat(em.events).hasSize(2);
    }

    @Test
    void recording_finops_sink_implements_interface() {
        RecordingFinOpsSink sink = new RecordingFinOpsSink();
        sink.record(CostMetrics.zero("r1"),
                FinOpsTag.of("retail", "prod", "cc", "owner", "r1"));
        assertThat(sink.entries).hasSize(1);
    }

    @Test
    void env_secret_provider_implements_interface_with_default_get() {
        SecretProvider provider = new SecretProvider() {
            @Override
            public String get(String name, String version) {
                return "value-of-" + name + "@" + version;
            }
        };
        // Convenience default method
        assertThat(provider.get("db-password")).isEqualTo("value-of-db-password@latest");
        assertThat(provider.get("db-password", "v2")).isEqualTo("value-of-db-password@v2");
    }

    // ---- fakes ----

    private static final class InMemoryBlobStore implements BlobStore {
        private final Map<String, byte[]> store = new HashMap<>();

        @Override public byte[] get(String uri) {
            byte[] b = store.get(uri);
            if (b == null) {
                throw new IllegalStateException("not found: " + uri);
            }
            return b.clone();
        }
        @Override public InputStream openInput(String uri) {
            return new ByteArrayInputStream(get(uri));
        }
        @Override public OutputStream openOutput(String uri) {
            return new ByteArrayOutputStream() {
                @Override public void close() {
                    store.put(uri, toByteArray());
                }
            };
        }
        @Override public void put(String uri, byte[] data) {
            store.put(uri, data.clone());
        }
        @Override public Iterator<String> list(String prefix) {
            return store.keySet().stream()
                    .filter(k -> k.startsWith(prefix))
                    .sorted()
                    .iterator();
        }
        @Override public boolean exists(String uri) {
            return store.containsKey(uri);
        }
        @Override public void delete(String uri) {
            store.remove(uri);
        }
        @Override public void copy(String src, String dst) {
            store.put(dst, store.get(src).clone());
        }
    }

    private static final class RecordingAuditPublisher implements AuditEventPublisher {
        final List<AuditRecord> published = new ArrayList<>();
        int flushCalls;
        @Override public void publish(AuditRecord record) { published.add(record); }
        @Override public void flush() { flushCalls++; }
    }

    private static final class RecordingLineageEmitter implements LineageEmitter {
        final List<LineageEvent> events = new ArrayList<>();
        @Override public void emit(LineageEvent event) { events.add(event); }
    }

    private static final class RecordingFinOpsSink implements FinOpsSink {
        record Entry(CostMetrics metrics, FinOpsTag tags) {}
        final List<Entry> entries = new ArrayList<>();
        @Override public void record(CostMetrics metrics, FinOpsTag tags) {
            entries.add(new Entry(metrics, tags));
        }
    }
}

package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.itsupport.FakeGcsServerContainer;
import com.google.cloud.storage.BucketInfo;
import com.google.cloud.storage.Storage;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Integration tests for {@link GcsBlobStore} exercised against a real GCS
 * emulator (fsouza/fake-gcs-server) via the it-support
 * {@link FakeGcsServerContainer} fixture.
 *
 * <p>Where {@code GcsBlobStoreTest} mocks the
 * {@link com.google.cloud.storage.Storage} client and asserts on the calls the
 * adapter issues, this IT drives the adapter end-to-end against the running
 * fake server: it creates a real bucket, then exercises the full
 * {@link com.enrichmeai.culvert.contracts.BlobStore} surface
 * ({@code put} / {@code openOutput} / {@code get} / {@code openInput} /
 * {@code exists} / {@code list} / {@code delete}) and asserts on the bytes and
 * URIs that actually come back from the emulator.
 *
 * <p>The fixture's {@link FakeGcsServerContainer#newClient()} builds a
 * {@link Storage} client pointed at the mapped emulator port with
 * {@link com.google.cloud.NoCredentials}. The same client is handed to the
 * {@link GcsBlobStore} under test, so creating the bucket on it and exercising
 * the adapter both hit the same in-memory server. {@link GcsBlobStore} owns and
 * closes that client via {@link GcsBlobStore#close()}, so the store is closed
 * once in {@link #tearDown()} for the whole class.
 *
 * <p>Sprint-10 deliverable (T10.4).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class GcsBlobStoreIT {

    @Container
    static final FakeGcsServerContainer GCS = new FakeGcsServerContainer();

    private static final String BUCKET = "culvert-it-bucket";

    private GcsBlobStore store;

    @BeforeAll
    void setUp() {
        // Build a client against the running emulator and create the bucket on
        // it before any adapter calls. The store takes ownership of this client.
        Storage storage = GCS.newClient();
        storage.create(BucketInfo.of(BUCKET));
        store = new GcsBlobStore(storage);
    }

    @AfterAll
    void tearDown() {
        // GcsBlobStore#close() closes the wrapped Storage client.
        if (store != null) {
            store.close();
        }
    }

    private static String uri(String objectName) {
        return GcsBlobStore.SCHEME + BUCKET + "/" + objectName;
    }

    @Test
    void putGetExistsDeleteRoundTrip() {
        String key = uri("round-trip/object.txt");
        byte[] payload = "hello fake-gcs".getBytes(StandardCharsets.UTF_8);

        // Absent before the write.
        assertThat(store.exists(key)).isFalse();

        // Write, then it exists and reads back identical bytes.
        store.put(key, payload);
        assertThat(store.exists(key)).isTrue();
        assertThat(store.get(key)).isEqualTo(payload);

        // Delete, then it is gone again. Delete is idempotent: a second delete
        // against the now-missing object must not throw.
        store.delete(key);
        assertThat(store.exists(key)).isFalse();
        store.delete(key);
    }

    @Test
    void getMissingObjectThrowsFileNotFound() {
        String key = uri("does-not-exist.txt");

        assertThat(store.exists(key)).isFalse();
        assertThatThrownBy(() -> store.get(key))
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(java.io.FileNotFoundException.class)
                .hasMessageContaining(key);
    }

    @Test
    void openOutputThenOpenInputStreamsBytes() throws IOException {
        String key = uri("streamed/payload.bin");
        byte[] payload = "streamed-content-via-channels".getBytes(StandardCharsets.UTF_8);

        // Streaming write: the write commits on close().
        try (OutputStream out = store.openOutput(key)) {
            out.write(payload);
        }

        assertThat(store.exists(key)).isTrue();

        // Streaming read back of the same bytes.
        byte[] read;
        try (InputStream in = store.openInput(key)) {
            read = in.readAllBytes();
        }
        assertThat(read).isEqualTo(payload);

        // get() must see the same bytes the stream wrote.
        assertThat(store.get(key)).isEqualTo(payload);

        store.delete(key);
    }

    @Test
    void listWithPrefixYieldsAbsoluteUris() {
        // Seed three objects: two under the listed prefix, one outside it.
        String a = uri("list-prefix/a.txt");
        String b = uri("list-prefix/b.txt");
        String other = uri("list-other/c.txt");
        store.put(a, "a".getBytes(StandardCharsets.UTF_8));
        store.put(b, "b".getBytes(StandardCharsets.UTF_8));
        store.put(other, "c".getBytes(StandardCharsets.UTF_8));

        Iterator<String> it = store.list(uri("list-prefix/"));
        List<String> found = new ArrayList<>();
        it.forEachRemaining(found::add);

        // Absolute gs:// URIs, only the two under the prefix, and the object
        // outside the prefix is excluded.
        assertThat(found)
                .containsExactlyInAnyOrder(a, b)
                .doesNotContain(other);

        store.delete(a);
        store.delete(b);
        store.delete(other);
    }
}

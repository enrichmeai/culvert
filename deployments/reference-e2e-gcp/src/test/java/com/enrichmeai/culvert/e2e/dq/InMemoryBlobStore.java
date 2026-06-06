package com.enrichmeai.culvert.e2e.dq;

import com.enrichmeai.culvert.contracts.BlobStore;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileNotFoundException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * In-memory {@link BlobStore} stub used by the S14 DQ E2E slice.
 *
 * <p>Stores bytes keyed by URI in a {@link LinkedHashMap}. Only the methods
 * needed by {@link com.enrichmeai.culvert.gcp.gcs.QuarantineHandler} are
 * implemented; all others throw {@link UnsupportedOperationException}.
 *
 * <h2>Live GCS URI pattern (for reference)</h2>
 * <p>In production the prefix passed to {@code QuarantineHandler} would be:
 * <pre>
 *   gs://&lt;error-bucket&gt;/errors/&lt;pipeline-id&gt;
 * </pre>
 * The handler then appends {@code /quarantine/&lt;runId&gt;/&lt;timestamp&gt;.jsonl}.
 * No credentials or network are required in this stub.
 *
 * <p>Sprint-14 / issue #82 (T14.5) stub — not a production BlobStore.
 */
final class InMemoryBlobStore implements BlobStore {

    /** Backing store: URI → bytes. */
    private final Map<String, byte[]> store = new LinkedHashMap<>();

    /** Returns an unmodifiable snapshot of all URIs written so far. */
    List<String> writtenUris() {
        return Collections.unmodifiableList(new ArrayList<>(store.keySet()));
    }

    /**
     * Returns the bytes stored at {@code uri}, or {@code null} if absent.
     * (Caller responsible for null-checking; this stub does not throw
     * FileNotFoundException for simplicity.)
     */
    byte[] getOrNull(String uri) {
        return store.get(uri);
    }

    @Override
    public byte[] get(String uri) {
        byte[] bytes = store.get(uri);
        if (bytes == null) {
            throw new RuntimeException(new FileNotFoundException("no object at: " + uri));
        }
        return bytes;
    }

    @Override
    public InputStream openInput(String uri) {
        return new ByteArrayInputStream(get(uri));
    }

    @Override
    public OutputStream openOutput(String uri) {
        return new ByteArrayOutputStream() {
            @Override
            public void close() {
                store.put(uri, toByteArray());
            }
        };
    }

    @Override
    public void put(String uri, byte[] data) {
        store.put(uri, data);
    }

    @Override
    public Iterator<String> list(String prefix) {
        return store.keySet().stream()
                .filter(k -> k.startsWith(prefix))
                .iterator();
    }

    @Override
    public boolean exists(String uri) {
        return store.containsKey(uri);
    }

    @Override
    public void delete(String uri) {
        store.remove(uri);
    }

    @Override
    public void copy(String src, String dst) {
        byte[] data = get(src);
        store.put(dst, data);
    }
}
